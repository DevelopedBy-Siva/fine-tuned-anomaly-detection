import os
import customtkinter as ctk
from tkinter import filedialog

import utils


class UI(ctk.CTkFrame):

    def __init__(self, root: ctk.CTk) -> None:
        super().__init__(root, fg_color=utils.BG_COLOR)
        self.__root = root
        self.log_data = []

        # Left Container
        frame_down = ctk.CTkFrame(self, fg_color="transparent")
        frame_down.grid(row=2, column=0, sticky="ew", pady=(20, 10))

        # Upload button
        upload_btn = ctk.CTkButton(
            frame_down,
            fg_color=utils.BUTTON_BG,
            text="Import File",
            hover_color=utils.BUTTON_HOVER,
            cursor="hand",
            command=self.__pick_file,
        )
        upload_btn.grid(column=2, row=0, padx=(20, 0), sticky="e")

        # Reset button
        reset_btn = ctk.CTkButton(
            frame_down,
            fg_color="transparent",
            border_width=1,
            border_color=utils.BORDER_COLOR,
            text="Reset",
            text_color=utils.COLOR_LIGHT,
            hover_color=utils.BUTTON_RESET_HOVER,
            cursor="hand",
            command=self.__reset,
        )
        reset_btn.grid(column=3, row=0, padx=(20, 0), sticky="e")

        self.__file_label = ctk.CTkLabel(frame_down, text="", anchor="e")
        self.__file_label.grid(column=1, row=0, sticky="e")

        frame_down.grid_columnconfigure(0, weight=1)

        # Right Container
        frame_top = ctk.CTkFrame(
            self,
            fg_color="transparent",
            border_width=1,
            border_color=utils.BORDER_COLOR,
        )
        frame_top.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        self.__log_report_placeholder = ctk.CTkLabel(
            frame_top,
            text="Please select a log file to view the result.",
            text_color=utils.COLOR_LIGHT,
        )

        self.__log_report_placeholder.grid(
            row=0, column=0, sticky="nsew", pady=5, padx=5
        )

        # Display log analysis report
        self.__log_report = ctk.CTkTextbox(
            frame_top, fg_color=utils.BG_COLOR, text_color=utils.COLOR_LIGHT
        )
        self.__log_report.grid(row=0, column=0, sticky="nsew", pady=5, padx=5)
        self.__log_report.grid_remove()

        frame_top.grid_rowconfigure(0, weight=1)
        frame_top.grid_columnconfigure(0, weight=1)

        # Header
        self.__frame_header = ctk.CTkFrame(self, fg_color="transparent")
        self.__frame_header.grid(column=0, row=0, sticky="we", pady=(10, 10))

        self.__log_entires_count = ctk.CTkLabel(
            self.__frame_header, text="", anchor="w", font=(utils.FONT_FAMILY, 14)
        )
        self.__log_entires_count.grid(column=0, row=0, sticky="ew")

        self.__anomaly_count = ctk.CTkLabel(
            self.__frame_header, text="", font=(utils.FONT_FAMILY, 14)
        )
        self.__anomaly_count.grid(column=1, row=0)

        self.__model_confidence = ctk.CTkLabel(
            self.__frame_header, text="", anchor="e", font=(utils.FONT_FAMILY, 14)
        )
        self.__model_confidence.grid(column=2, row=0, sticky="ew")

        # hide header
        self.__frame_header.grid_remove()

        self.__frame_header.grid_columnconfigure(0, weight=1)
        self.__frame_header.grid_columnconfigure(1, weight=1)
        self.__frame_header.grid_columnconfigure(2, weight=1)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    # Pick the log file
    def __pick_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Log", "*.log")])
        self.__log_report_placeholder.grid_remove()
        if file_path:
            # Get file name
            file_name = os.path.basename(file_path)
            self.__file_label.configure(text=f"You’ve selected:   '{file_name}'")
            self.__log_report.grid()

            with open(file_path, "r") as f:
                for idx, entry in enumerate(f):
                    self.log_data.append(entry)
                    self.__log_report.insert("end", f"{idx+1}.     {entry.strip()}\n\n")

            # Result
            log_entries = len(self.log_data)
            # TODO: Retrieve data from the model
            anomaly_count = 150
            model_confidence = 93

            self.__log_entires_count.configure(text=f"Log Entries:   {log_entries}")
            self.__anomaly_count.configure(
                text=f"Anomalies Detected:   {anomaly_count}", text_color="#e50000"
            )
            self.__model_confidence.configure(
                text=f"Model Confidence:   {model_confidence}%",
                text_color="#80B800" if model_confidence >= 80 else "#F79C0E",
            )

            # show header
            self.__frame_header.grid()

            # Textbox disabled
            self.__log_report.configure(state="disabled")
        # Focus back to window
        self.__root.focus_force()

    # Reset the app
    def __reset(self):
        self.log_data = []
        self.__file_label.configure(text="")
        self.__log_entires_count.configure(text="")
        self.__anomaly_count.configure(text="")
        self.__model_confidence.configure(text="")
        self.__frame_header.grid_remove()
        self.__log_report.grid_remove()
        self.__log_report_placeholder.grid()
