import customtkinter as ctk
from PIL import Image

import utils


class UI(ctk.CTkFrame):

    def __init__(self, root: ctk.CTkFrame) -> None:
        super().__init__(root, fg_color=utils.BG_COLOR)

        # Left Container
        l_width = 300
        frame_l = ctk.CTkFrame(self, width=l_width, fg_color=utils.BG_COLOR)
        frame_l.grid(row=0, column=0, sticky="nsew")
        frame_l.grid_propagate(False)

        # Upload button icon
        ico = Image.open("./add_ico.png").resize((100, 100))
        ico = ctk.CTkImage(light_image=ico, dark_image=ico, size=(100, 100))

        # Upload button
        upload_btn = ctk.CTkButton(
            frame_l,
            fg_color="transparent",
            image=ico,
            text="",
            border_width=1,
            border_color=utils.COLOR_LIGHT,
            hover_color=utils.COLOR_HOVER,
            cursor="hand",
        )
        upload_btn.grid(column=0, row=0, padx=20, pady=20, sticky="ew")

        frame_l.grid_rowconfigure(0, weight=1)
        frame_l.grid_columnconfigure(0, weight=1)

        # Right Container
        frame_r = ctk.CTkFrame(
            self,
            fg_color=utils.BG_COLOR,
            border_width=1,
            border_color=utils.COLOR_LIGHT,
        )
        frame_r.grid(row=0, column=1, sticky="nsew")

        # Display log analysis report
        textbox = ctk.CTkTextbox(frame_r, fg_color=utils.BG_COLOR)
        textbox.grid(row=0, column=0, sticky="nsew", pady=5, padx=5)

        # TODO
        # Test Data
        for _ in range(100):
            textbox.insert("end", f"Line\n")

        # Textbox disabled
        textbox.configure(state="disabled")

        frame_r.grid_rowconfigure(0, weight=1)
        frame_r.grid_columnconfigure(0, weight=1)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
