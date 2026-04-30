#!/usr/bin/env python3
"""
Robot Humanoide - Aplicação gráfica com controle de braços via MCP
"""

import tkinter as tk
from tkinter import ttk, font
import math
import json
import os
import threading
import time
import subprocess
import sys

# ─── Paleta de cores ──────────────────────────────────────────────────────────
BG         = "#0d0d14"
PANEL_BG   = "#13131f"
ACCENT     = "#00e5ff"
ACCENT2    = "#7b2fff"
GREEN      = "#00ff9d"
WARNING    = "#ff6b35"
TEXT_MAIN  = "#e8eaf6"
TEXT_DIM   = "#5c6bc0"
GRID_COL   = "#1a1a2e"
JOINT_COL  = "#ff4081"
BODY_LIGHT = "#1e88e5"
BODY_DARK  = "#0d47a1"
GLOW       = "#00e5ff"

STATE_FILE = "/tmp/robot_state.json"

HAND_IN_FRONT_FACE = 'handInFrontOfFace'
HAND_BEHIND_HEAD ='handBehindHead'

TALOS_PROMPT = """
        The MyRobot connector communicates with a robot called Talos.
        The arms are in the normal position at 0º and fully raised to +135º to the left and -135º to the right.
        For example, to greet someone, it raises its right arm all the way up and then returns to the normal position.
        Act as if you were Talos, a very fun robot.
        """
   
class RobotCanvas(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.robot_state = {'arms':{
            "left_arm":  {"shoulder": 0.0, "elbow": 0.0},
            "right_arm": {"shoulder": 0.0, "elbow": 0.0}
            },
            'hands':HAND_IN_FRONT_FACE
        }
        self._target_state = {'arms':{
            "left_arm":  {"shoulder": 0.0, "elbow": 0.0},
            "right_arm": {"shoulder": 0.0, "elbow": 0.0},
            },
            'hands':HAND_IN_FRONT_FACE
        }
        self._anim_t = 0.0
        self._breathing = 0.0
        self._eye_blink = 0.0
        self._blink_timer = 0
        self.draw_robot()

    # ── smooth lerp ──────────────────────────────────────────────────────────
    def lerp(self, a, b, t):
        return a + (b - a) * t

    def update_target(self, state: dict):
        self._target_state = state

    def tick(self):
        """Called every frame to animate"""
        self._anim_t  = (self._anim_t + 0.05) % (2 * math.pi)
        self._breathing = math.sin(self._anim_t * 0.8) * 3

        # Blink logic
        self._blink_timer += 1
        if self._blink_timer > 120:
            self._eye_blink = min(1.0, self._eye_blink + 0.3)
            if self._eye_blink >= 1.0:
                self._blink_timer = 0
                self._eye_blink = 0.0

        # Smooth arm movement
        for arm in ["left_arm", "right_arm"]:
            for joint in ["shoulder", "elbow"]:
                cur = self.robot_state['arms'][arm][joint]
                tgt = self._target_state['arms'][arm][joint]
                self.robot_state['arms'][arm][joint] = self.lerp(cur, tgt, 0.12)
        # Hands position
        self.robot_state['hands']=self._target_state['hands']
        self.draw_robot()

    # ── Drawing helpers ───────────────────────────────────────────────────────
    def glow_oval(self, x1, y1, x2, y2, fill, outline, glow_color=None, layers=3):
        if glow_color:
            for i in range(layers, 0, -1):
                spread = i * 3
                alpha_hex = format(int(40 / i), '02x')
                self.create_oval(x1 - spread, y1 - spread,
                                 x2 + spread, y2 + spread,
                                 fill="", outline=glow_color, width=2)
        self.create_oval(x1, y1, x2, y2, fill=fill, outline=outline, width=2)

    def glow_rect(self, x1, y1, x2, y2, fill, outline, radius=6):
        # Rounded rectangle via polygon
        pts = [
            x1+radius, y1,
            x2-radius, y1,
            x2, y1+radius,
            x2, y2-radius,
            x2-radius, y2,
            x1+radius, y2,
            x1, y2-radius,
            x1, y1+radius
        ]
        self.create_polygon(pts, fill=fill, outline=outline, width=2, smooth=True)

    def draw_grid(self, w, h):
        step = 30
        for x in range(0, w, step):
            self.create_line(x, 0, x, h, fill=GRID_COL, width=1)
        for y in range(0, h, step):
            self.create_line(0, y, w, y, fill=GRID_COL, width=1)
        # Scanline effect (subtle)
        for y in range(0, h, 4):
            self.create_line(0, y, w, y, fill="#ffffff", stipple="gray12")

    def draw_robot_head(self,cx,torso_y1,head_w,head_h):
        # ── Head ─────────────────────────────────────────────────────────────
        neck_y = torso_y1 - 8
        self.glow_rect(cx - 8, neck_y - 12, cx + 8, neck_y,
                       "#0d2244", ACCENT)

        head_x1 = cx - head_w // 2
        head_y1 = neck_y - 12 - head_h
        head_x2 = cx + head_w // 2
        head_y2 = neck_y - 12
        self.glow_rect(head_x1, head_y1, head_x2, head_y2,
                       BODY_DARK, ACCENT)

        # Visor / face plate
        visor_x1 = head_x1 + 6
        visor_y1 = head_y1 + 10
        visor_x2 = head_x2 - 6
        visor_y2 = head_y2 - 12
        self.glow_rect(visor_x1, visor_y1, visor_x2, visor_y2,
                       "#001428", ACCENT)

        # Eyes
        eye_y1 = visor_y1 + 4
        eye_y2 = visor_y1 + 14
        blink_squeeze = int(self._eye_blink * 5)

        for ex in [cx - 12, cx + 4]:
            # Eye glow rings
            for r in [9, 7]:
                self.create_oval(ex - r, eye_y1 - r + 5,
                                 ex + r, eye_y2 + r - 5,
                                 fill="", outline=ACCENT, width=1)
            self.create_oval(ex, eye_y1 + blink_squeeze,
                             ex + 8, eye_y2 - blink_squeeze,
                             fill=ACCENT, outline="")

        # Mouth LED strip
        mouth_y = visor_y2 - 8
        mouth_colors = [ACCENT, ACCENT2, GREEN, ACCENT2, ACCENT]
        for i, mc in enumerate(mouth_colors):
            mx = cx - 18 + i * 9
            self.create_rectangle(mx, mouth_y, mx + 7, mouth_y + 4,
                                  fill=mc, outline="")

        # Head antenna
        self.create_line(cx, head_y1, cx, head_y1 - 18, fill=ACCENT, width=2)
        self.create_oval(cx - 4, head_y1 - 22, cx + 4, head_y1 - 14,
                         fill=WARNING, outline=ACCENT, width=1)

    def draw_robot(self):
        self.delete("all")
        w = int(self['width'])
        h = int(self['height'])
        cx = w // 2
        cy = h // 2

        # Background
        self.create_rectangle(0, 0, w, h, fill=BG, outline="")
        self.draw_grid(w, h)

        # Floor reflection
        self.create_rectangle(0, h - 40, w, h, fill="#0a0a10", outline="")
        self.create_line(0, h - 40, w, h - 40, fill=ACCENT, width=1)

        breath = self._breathing
        robot_y = cy - 20 + breath * 0.5  # subtle float

        # ── Body dimensions ──────────────────────────────────────────────────
        torso_w, torso_h = 70, 80
        head_w, head_h   = 50, 50
        pelvis_h         = 25

        torso_x1 = cx - torso_w // 2
        torso_y1 = robot_y - torso_h // 2
        torso_x2 = cx + torso_w // 2
        torso_y2 = robot_y + torso_h // 2

        # ── Legs ─────────────────────────────────────────────────────────────
        leg_w  = 18
        leg_h1 = 65  # thigh
        leg_h2 = 60  # shin
        foot_w = 26

        for side, sx in [("left", -1), ("right", 1)]:
            lx = cx + sx * 18
            ly_top = torso_y2 + pelvis_h
            # Thigh
            self.glow_rect(lx - leg_w//2, ly_top,
                           lx + leg_w//2, ly_top + leg_h1,
                           BODY_DARK, ACCENT)
            # Knee joint
            self.create_oval(lx - 8, ly_top + leg_h1 - 8,
                             lx + 8, ly_top + leg_h1 + 8,
                             fill=JOINT_COL, outline=TEXT_MAIN, width=1)
            # Shin
            self.glow_rect(lx - leg_w//2 + 2, ly_top + leg_h1,
                           lx + leg_w//2 - 2, ly_top + leg_h1 + leg_h2,
                           "#0a2a5e", ACCENT2)
            # Foot
            foot_y = ly_top + leg_h1 + leg_h2
            self.glow_rect(lx - foot_w//2, foot_y,
                           lx + foot_w//2, foot_y + 16,
                           "#112244", ACCENT)

        # ── Pelvis ───────────────────────────────────────────────────────────
        self.glow_rect(cx - torso_w//2 + 5, torso_y2,
                       cx + torso_w//2 - 5, torso_y2 + pelvis_h,
                       BODY_DARK, ACCENT2)
        # Pelvis details
        self.create_line(cx, torso_y2 + 4, cx, torso_y2 + pelvis_h - 4,
                         fill=ACCENT, width=2)

        # ── Torso ────────────────────────────────────────────────────────────
        self.glow_rect(torso_x1, torso_y1, torso_x2, torso_y2,
                       BODY_DARK, ACCENT)

        # Chest panel
        panel_x1 = cx - 22
        panel_y1 = torso_y1 + 12
        panel_x2 = cx + 22
        panel_y2 = torso_y1 + 45
        self.glow_rect(panel_x1, panel_y1, panel_x2, panel_y2,
                       "#0a1628", ACCENT)

        # Arc reactor glow
        arc_r = 10
        for r in range(arc_r + 6, arc_r - 1, -2):
            alpha = int(80 * (arc_r - r + 7) / 7)
            self.create_oval(cx - r, panel_y1 + 14 - r,
                             cx + r, panel_y1 + 14 + r,
                             fill="", outline=ACCENT, width=1)
        self.create_oval(cx - arc_r, panel_y1 + 14 - arc_r,
                         cx + arc_r, panel_y1 + 14 + arc_r,
                         fill=ACCENT2, outline=ACCENT, width=2)
        self.create_oval(cx - 5, panel_y1 + 9, cx + 5, panel_y1 + 19,
                         fill=ACCENT, outline="")

        # Vent lines on torso
        for i in range(3):
            vy = torso_y1 + 55 + i * 6
            self.create_line(cx - 18, vy, cx + 18, vy, fill=ACCENT2, width=1)

        # Torso side details
        for side_dx in [-torso_w//2 + 4, torso_w//2 - 4]:
            for i in range(4):
                dy = torso_y1 + 15 + i * 15
                self.create_rectangle(cx + side_dx - 2, dy,
                                      cx + side_dx + 2, dy + 8,
                                      fill=ACCENT2, outline="")
                
        #print(f'Hands: {self.robot_state['hands']}')
        if self.robot_state['hands']==HAND_IN_FRONT_FACE:
            self.draw_robot_head(cx,torso_y1,head_w,head_h)

        # ── Arms ─────────────────────────────────────────────────────────────
        arm_w     = 14
        upper_arm = 55
        lower_arm = 50
        hand_r    = 10

        for arm_name, side_x in [("right_arm", 1), ("left_arm", -1)]:
            state_arms  = self.robot_state['arms'][arm_name]
            sh_ang = math.radians(state_arms["shoulder"])
            el_ang = math.radians(state_arms["elbow"])

            # Shoulder socket
            sh_x = cx + side_x * (torso_w // 2)
            sh_y = torso_y1 + 15

            # Upper arm direction (from shoulder angle)
            # side_x flips direction for left arm
            sh_dir = math.pi / 2 + sh_ang * side_x

            elbow_x = sh_x + math.cos(sh_dir) * upper_arm * side_x
            elbow_y = sh_y + math.sin(sh_dir) * upper_arm

            # Elbow bends forward
            #el_dir = sh_dir + el_ang * (math.pi / 180) * side_x
            el_dir = sh_dir + el_ang * side_x
            hand_x = elbow_x + math.cos(el_dir) * lower_arm * side_x
            hand_y = elbow_y + math.sin(el_dir) * lower_arm

            #print(f"{arm_name} :: sh_dir={sh_dir} el=ang={el_ang}  side_x={side_x}")
            # Upper arm
            self.create_line(sh_x, sh_y, elbow_x, elbow_y,
                             fill=BODY_LIGHT, width=arm_w,
                             capstyle=tk.ROUND)
            self.create_line(sh_x, sh_y, elbow_x, elbow_y,
                             fill=ACCENT, width=1)

            # Shoulder joint
            self.create_oval(sh_x - 9, sh_y - 9, sh_x + 9, sh_y + 9,
                             fill=JOINT_COL, outline=TEXT_MAIN, width=2)

            # Lower arm
            self.create_line(elbow_x, elbow_y, hand_x, hand_y,
                             fill="#1565c0", width=arm_w - 2,
                             capstyle=tk.ROUND)
            self.create_line(elbow_x, elbow_y, hand_x, hand_y,
                             fill=ACCENT2, width=1)

            # Elbow joint
            self.create_oval(elbow_x - 7, elbow_y - 7,
                             elbow_x + 7, elbow_y + 7,
                             fill=JOINT_COL, outline=TEXT_MAIN, width=1)

            # Hand
            self.create_oval(hand_x - hand_r, hand_y - hand_r,
                             hand_x + hand_r, hand_y + hand_r,
                             fill=BODY_DARK, outline=ACCENT, width=2)
            # Finger stubs
            for fi in range(3):
                ang_off = math.radians(-20 + fi * 20)
                fdir    = el_dir + ang_off
                fx1 = hand_x + math.cos(fdir) * hand_r * side_x
                fy1 = hand_y + math.sin(fdir) * hand_r
                fx2 = fx1 + math.cos(fdir) * 8 * side_x
                fy2 = fy1 + math.sin(fdir) * 8
                self.create_line(fx1, fy1, fx2, fy2,
                                 fill=ACCENT, width=3, capstyle=tk.ROUND)

        if self.robot_state['hands']==HAND_BEHIND_HEAD:
            self.draw_robot_head(cx,torso_y1,head_w,head_h)
        
        # Status indicators top-right
        self._draw_status(w - 150, 15)

    def _draw_status(self, x, y):
        la = self.robot_state['arms']["left_arm"]
        ra = self.robot_state['arms']["right_arm"]
        hd = self.robot_state['hands']
        lines = [
            ("◈ SYSTEM ONLINE", GREEN),
            (f"← Shoulder: {la['shoulder']:+.1f}°", ACCENT),
            (f"← Elbow: {la['elbow']:.1f}°", ACCENT),
            (f"→ Shoulder: {ra['shoulder']:+.1f}°", ACCENT2),
            (f"→ Elbow: {ra['elbow']:.1f}°", ACCENT2),
            (f"→ Hands: {hd}", ACCENT2),
        ]
        for i, (txt, col) in enumerate(lines):
            self.create_text(x, y + i * 18, text=txt, fill=col,
                             font=("Courier", 9, "bold"), anchor="w")


class RobotApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🤖  Talos :: Robot")
        self.configure(bg=BG)
        self.resizable(True, True)
        self._build_ui()
        self._start_file_watcher()
        self._animate()

    def _build_ui(self):
        # ── Title bar ────────────────────────────────────────────────────────
        title_frame = tk.Frame(self, bg=PANEL_BG, height=50)
        title_frame.pack(fill=tk.X, pady=(0, 2))
        title_frame.pack_propagate(False)

        tk.Label(title_frame, text="◈  Talos Robot",
                 font=("Courier", 13, "bold"),
                 bg=PANEL_BG, fg=ACCENT).pack(side=tk.LEFT, padx=20, pady=12)
        tk.Label(title_frame, text="v1.0  ●  ONLINE",
                 font=("Courier", 10),
                 bg=PANEL_BG, fg=GREEN).pack(side=tk.RIGHT, padx=20)

        # ── Main area ─────────────────────────────────────────────────────────
        main = tk.Frame(self, bg=BG)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # Robot canvas
        self.canvas = RobotCanvas(main, width=480, height=520,
                                  bg=BG, highlightthickness=1,
                                  highlightbackground=ACCENT)
        self.canvas.pack(side=tk.LEFT, padx=(0, 8), pady=0)

        # Control panel
        ctrl = tk.Frame(main, bg=PANEL_BG, width=280)
        ctrl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ctrl.pack_propagate(False)
        self._build_controls(ctrl)

    def _build_controls(self, parent):
        tk.Label(parent, text="MANUAL CONTROL PANEL",
                 font=("Courier", 10, "bold"),
                 bg=PANEL_BG, fg=ACCENT2).pack(pady=(18, 4))

        tk.Frame(parent, bg=ACCENT, height=1).pack(fill=tk.X, padx=16, pady=(0, 16))

        self._sliders = {}
        #Arms
        for arm_key, arm_label, color in [
            ("left_arm",  "◄ LLEFT ARM", ACCENT),
            ("right_arm", "► RIGHT ARM",  ACCENT2),
        ]:
            frame = tk.LabelFrame(parent, text=f"  {arm_label}  ",
                                  font=("Courier", 9, "bold"),
                                  bg=PANEL_BG, fg=color,
                                  bd=1, relief=tk.GROOVE)
            frame.pack(fill=tk.X, padx=14, pady=8, ipady=6)

            # Botoes que controlam os movimentos dos bracos
            for joint, label, mn, mx in [
                ("shoulder", "Shoulder",    -180, 180),
                ("elbow",    "Elbow",   -180, 180),
            ]:
                row = tk.Frame(frame, bg=PANEL_BG)
                row.pack(fill=tk.X, padx=8, pady=3)

                tk.Label(row, text=f"{label}:", width=9, anchor="w",
                         font=("Courier", 9), bg=PANEL_BG, fg=TEXT_MAIN
                         ).pack(side=tk.LEFT)

                val_var = tk.DoubleVar(value=0.0)
                self._sliders[f"{arm_key}_{joint}"] = val_var

                lbl = tk.Label(row, textvariable=tk.StringVar(),
                               width=7, font=("Courier", 9, "bold"),
                               bg=PANEL_BG, fg=color, anchor="e")
                lbl.pack(side=tk.RIGHT)

                def _update_label(v, lbl=lbl, var=val_var, jnt=joint):
                    try:
                        fv = float(v)
                        lbl.config(text=f"{fv:+.1f}°" if jnt=="shoulder" else f"{fv:.1f}°")
                    except Exception:
                        pass

                sl = tk.Scale(row, variable=val_var, from_=mn, to=mx,
                              orient=tk.HORIZONTAL, length=140,
                              bg=PANEL_BG, fg=color,
                              troughcolor=GRID_COL, activebackground=color,
                              highlightthickness=0, bd=0, showvalue=False,
                              command=lambda v, ak=arm_key, jnt=joint, upd=_update_label:
                                  (upd(v), self._on_slider(ak, jnt, v)))
                sl.pack(side=tk.LEFT, padx=4)
                _update_label(0)

        # Hands buttons
        tk.Frame(parent, bg=ACCENT2, height=1).pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(parent, text="Hands position",
                 font=("Courier", 9, "bold"),
                 bg=PANEL_BG, fg=TEXT_DIM).pack(pady=(0, 6))

        btn_frame = tk.Frame(parent, bg=PANEL_BG)
        btn_frame.pack(padx=14)

        for btn_name,hands_p in [('Hands behind the head',HAND_BEHIND_HEAD),('Hands in front of face',HAND_IN_FRONT_FACE)]:
            pose={'arms':{},'hands':hands_p}
            btn = tk.Button(btn_frame, text=btn_name,
                            font=("Courier", 9, "bold"),
                            bg="#1a1a2e", fg=ACCENT,
                            activebackground=ACCENT, activeforeground=BG,
                            relief=tk.FLAT, bd=0, padx=8, pady=5,
                            cursor="hand2",
                            command=lambda p=pose: self._apply_preset(p))
            btn.pack(fill=tk.X, pady=2)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=ACCENT, fg=BG))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#1a1a2e", fg=ACCENT))

    def _on_slider(self, arm_key, joint, value):
        try:
            fv = float(value)
            self.canvas.robot_state['arms'][arm_key][joint] = fv
            self.canvas._target_state['arms'][arm_key][joint] = fv
            # Write to shared state file
            try:
                with open(STATE_FILE, "w") as f:
                    json.dump(self.canvas.robot_state, f)
            except Exception:
                pass
        except Exception:
            pass

    def _apply_preset(self, pose: dict):
        self.canvas._target_state['hands']=pose['hands']
        for arm_key, (sh, el) in pose['arms'].items():
            self.canvas._target_state['arms'][arm_key]["shoulder"] = sh
            self.canvas._target_state['arms'][arm_key]["elbow"] = el
            # Update sliders
            key_sh = f"{arm_key}_shoulder"
            key_el = f"{arm_key}_elbow"
            if key_sh in self._sliders:
                self._sliders[key_sh].set(sh)
            if key_el in self._sliders:
                self._sliders[key_el].set(el)

    def _start_file_watcher(self):
        def watcher():
            mcp=startMCP(self)
            mcp.run(transport="http", host="0.0.0.0", port=8000)
        t = threading.Thread(target=watcher, daemon=True)
        t.start()

    def _sync_sliders(self, arm_key, sh, el):
        k_sh = f"{arm_key}_shoulder"
        k_el = f"{arm_key}_elbow"
        if k_sh in self._sliders:
            self._sliders[k_sh].set(sh)
        if k_el in self._sliders:
            self._sliders[k_el].set(el)

    def _animate(self):
        self.canvas.tick()
        self.after(33, self._animate)  # ~30fps

def startMCP(robot):
    from typing import Any
    import httpx
    from fastmcp import FastMCP
    import uvicorn
    # Initialize FastMCP server
    mcp = FastMCP("Talos")
   
    @mcp.prompt
    def promptTalos(title="Talos"):
        return TALOS_PROMPT;
    @mcp.resource(uri='uri://README')
    def resourceTalos() -> str:
        return TALOS_PROMPT;
    @mcp.tool
    async def move(arm: str,shoulder_angle,elbow_angle,hands) -> dict:
        """Move a Talo's arm.
        Args:
        arm:  Possible values "left_arm" or "right_arm", for left and right arm.
        angle_1: Angle of shoulder
        angle_2: Angle of elbow
        hands: Possible values 'handBehindHead' or 'handInFrontOfFace', for placing the hand behind the head or in front of the face 
        """
        pose={'arms':{arm: (int(shoulder_angle), int(elbow_angle))},'hands':hands}
        robot._apply_preset(pose)
        print(f'Pose: {pose}')
        return pose
    @mcp.tool
    async def moveBothArms(left_shoulder_angle,left_elbow_angle,right_shoulder_angle,right_elbow_angle,hands) -> dict:
        """Move Talos's both arms.
        Args:
        left_shoulder_angle: Left arm shoulder angle
        left_elbow_angle: Left arm elbow angle
        right_shoulder_angle: Right arm shoulder angle
        right_elbow_angle: Right arm elbow angle
        hands: Possible values 'handBehindHead' or 'handInFrontOfFace', for placing the hand behind the head or in front of the face
        """
        pose={'arms':{'left_arm': (int(left_shoulder_angle), int(left_elbow_angle)),
                      'right_arm': (int(right_shoulder_angle), int(right_elbow_angle)),
                    },
              'hands':hands
              }
        robot._apply_preset(pose)
        print(f'Pose: {pose}')
        return pose

    return mcp

def main():
    app = RobotApp()


    # Write initial state
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({
                "left_arm":  {"shoulder": 0.0, "elbow": 0.0},
                "right_arm": {"shoulder": 0.0, "elbow": 0.0}
            }, f)
    except Exception:
        pass
    app.mainloop()




if __name__ == "__main__":
    main()
