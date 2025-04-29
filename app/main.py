import customtkinter as ctk

import utils
from ui import UI


def main():
    # Init the window
    root = ctk.CTk()
    root.title(utils.APP_NAME)
    root.minsize(width=utils.WIDTH, height=utils.HEIGHT)
    root.resizable(False, False)  # don't allow resize
    root.config(background=utils.BG_COLOR)

    _ = UI(root)  # Init the UI
    _.grid(row=0, column=0, sticky="nsew", padx=40, pady=(30, 30))

    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)

    root.mainloop()


if __name__ == "__main__":
    main()
