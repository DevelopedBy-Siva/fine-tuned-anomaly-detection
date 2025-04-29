import os
import customtkinter as ctk
from tkinter import filedialog

import utils
from anomaly_detector import AnomalyDetector

PLACEHOLDER = "Please select a log file to view the result."


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
            text=PLACEHOLDER,
            text_color=utils.COLOR_LIGHT,
        )

        self.__log_report_placeholder.grid(
            row=0, column=0, sticky="nsew", pady=5, padx=5
        )

        # Display log analysis report
        self.__log_report = ctk.CTkScrollableFrame(frame_top, fg_color=utils.BG_COLOR)
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
        if not file_path:
            return
        try:
            # reset when new file is selected
            self.__reset(placeholder_txt="📖 Reading log file....")
            self.__root.update_idletasks()

            # Get file name
            file_name = os.path.basename(file_path)
            self.__file_label.configure(text=f"You’ve selected:   '{file_name}'")
            self.__log_report.grid()

            with open(file_path, "r") as f:
                self.log_data = f.readlines()

            self.__log_report_placeholder.configure(text="🧠 Looking for anomalies...")
            self.__root.update_idletasks()

            anomaly_detector = AnomalyDetector(self.log_data)
            log_count, anomaly_count, model_confidence, flagged_logs = (
                anomaly_detector.detect()
            )

            for idx, entry in enumerate(flagged_logs):

                each_log_index = ctk.CTkLabel(
                    self.__log_report,
                    text=f"{idx + 1}.",
                    anchor="nw",
                    text_color=utils.COLOR_DULL,
                    justify="left",
                )
                each_log_index.grid(
                    row=idx, column=0, sticky="w", padx=(5, 10), pady=15
                )

                each_log_txt = ctk.CTkLabel(
                    self.__log_report,
                    text=f"{entry.strip()}",
                    anchor="nw",
                    text_color=utils.COLOR_LIGHT,
                    wraplength=860,
                    justify="left",
                )
                each_log_txt.grid(row=idx, column=1, sticky="w", padx=5, pady=2)

            self.__log_entires_count.configure(text=f"Log Entries:   {log_count}")
            self.__anomaly_count.configure(
                text=f"Anomalies Detected:   {anomaly_count}", text_color="#e50000"
            )
            self.__model_confidence.configure(
                text=f"Model Confidence:   {model_confidence}%",
                text_color="#80B800" if model_confidence >= 80 else "#F79C0E",
            )

            # show header
            self.__frame_header.grid()
        except:
            # reset if something goes wrong in rendering a UI
            self.__reset(placeholder_txt="⚠️ Something went wrong.")

        # Focus back to window
        self.__root.focus_force()

    # Reset the app
    def __reset(self, placeholder_txt=PLACEHOLDER):
        self.log_data = []

        for widget in self.__log_report.winfo_children():
            widget.destroy()

        self.__file_label.configure(text="")
        self.__log_entires_count.configure(text="")
        self.__anomaly_count.configure(text="")
        self.__model_confidence.configure(text="")

        self.__frame_header.grid_remove()

        self.__log_report_placeholder.configure(text=placeholder_txt)
        self.__log_report_placeholder.grid()
        self.__log_report.grid_remove()

        self.__root.update_idletasks()
