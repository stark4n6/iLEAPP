import customtkinter as ctk
from PIL import Image, ImageTk, ImageOps
import os
from tkinter import messagebox, filedialog
import json
import scripts.plugin_loader as plugin_loader

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("iLEAPP GUI")
        self.geometry("1000x600")
        self.resizable(False, False)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        os.makedirs("assets", exist_ok=True)

        # Initialize instance variables to store StringVar objects for case data
        self.casedata = {
            'Case Number': ctk.StringVar(),
            'Agency': ctk.StringVar(),
            'Agency Logo Path': ctk.StringVar(),
            'Examiner': ctk.StringVar()
        }

        # Initialize class-level variables
        self.current_frame_name = None
        
        # Instantiate PluginLoader and populate artifact list from it
        self.plugin_loader = plugin_loader.PluginLoader()
        self.artifact_list = sorted([plugin.name for plugin in self.plugin_loader.plugins])
        self.artifact_widgets = {}
        self.module_count_var = ctk.StringVar()

        # --- Navigation Frame ---
        self.navigation_frame = ctk.CTkFrame(self, corner_radius=0)
        self.navigation_frame.grid(row=0, column=0, sticky="nsew")
        self.navigation_frame.grid_rowconfigure(7, weight=1)
        self.navigation_frame.grid_rowconfigure(8, weight=0)
        self.navigation_frame.grid_rowconfigure(9, weight=0)

        # Top Logo Frame
        self.top_logo_frame = ctk.CTkFrame(self.navigation_frame, corner_radius=10, fg_color=("gray80", "gray15"))
        self.top_logo_frame.grid(row=0, column=0, padx=10, pady=(20, 10), sticky="ew")
        self.top_logo_frame.grid_columnconfigure(0, weight=1)

        self.ileapp_logo_image = self._load_ctk_image("assets/iLEAPP_logo.png", size=(200, 43), invert_for_dark=False)
        self.ileapp_logo_label = ctk.CTkLabel(self.top_logo_frame, text="", image=self.ileapp_logo_image)
        self.ileapp_logo_label.grid(row=0, column=0, padx=10, pady=10)

        self.home_button = ctk.CTkButton(self.navigation_frame, corner_radius=0, height=80, border_spacing=10, text="Home",
                                         fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
                                         image=self._load_ctk_image("assets/home.png", size=(20, 20), invert_for_dark=True), anchor="w",
                                         command=lambda: self.handle_navigation("home"))
        self.home_button.grid(row=1, column=0, sticky="ew")

        self.input_output_button = ctk.CTkButton(self.navigation_frame, corner_radius=0, height=80, border_spacing=10, text="Input/Output",
                                                 fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
                                                 image=self._load_ctk_image("assets/folder-plus.png", size=(20, 20), invert_for_dark=True), anchor="w",
                                                 command=lambda: self.handle_navigation("input_output"))
        self.input_output_button.grid(row=2, column=0, sticky="ew")

        self.artifacts_button = ctk.CTkButton(self.navigation_frame, corner_radius=0, height=80, border_spacing=10, text="Artifacts to Process",
                                              fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
                                              image=self._load_ctk_image("assets/check-square.png", size=(20, 20), invert_for_dark=True), anchor="w",
                                              command=lambda: self.handle_navigation("artifacts"))
        self.artifacts_button.grid(row=3, column=0, sticky="ew")

        self.case_data_button = ctk.CTkButton(self.navigation_frame, corner_radius=0, height=80, border_spacing=10, text="Case Data",
                                             fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
                                             image=self._load_ctk_image("assets/settings.png", size=(20, 20), invert_for_dark=True), anchor="w",
                                             command=lambda: self.handle_navigation("case_data"))
        self.case_data_button.grid(row=4, column=0, sticky="ew")

        # Bottom Logo Frame
        self.bottom_logo_frame = ctk.CTkFrame(self.navigation_frame, corner_radius=10, fg_color=("gray80", "gray15"))
        self.bottom_logo_frame.grid(row=8, column=0, padx=10, pady=(10, 10), sticky="ew")
        self.bottom_logo_frame.grid_columnconfigure(0, weight=1)

        self.new_placeholder_image = self._load_ctk_image("assets/leapps_i_logo.png", size=(200, 93), invert_for_dark=False)
        self.new_placeholder_label = ctk.CTkLabel(self.bottom_logo_frame, text="", image=self.new_placeholder_image)
        self.new_placeholder_label.grid(row=0, column=0, padx=10, pady=10)

        # --- Appearance Mode Toggle ---
        self.appearance_mode_frame = ctk.CTkFrame(self.navigation_frame, fg_color="transparent")
        self.appearance_mode_frame.grid(row=9, column=0, padx=20, pady=20, sticky="s")
        self.appearance_mode_frame.grid_columnconfigure(0, weight=0)
        self.appearance_mode_frame.grid_columnconfigure(1, weight=1)

        self.appearance_icon_label = ctk.CTkLabel(self.appearance_mode_frame, text="",
                                             image=self._load_ctk_image("assets/moon.png", size=(20, 20), invert_for_dark=True))
        self.appearance_icon_label.grid(row=0, column=0, padx=(0, 5))

        initial_appearance_mode = ctk.get_appearance_mode()
        switch_initial_value = "on" if initial_appearance_mode == "Dark" else "off"

        self.appearance_mode_switch_var = ctk.StringVar(value=switch_initial_value)
        self.appearance_mode_switch = ctk.CTkSwitch(self.appearance_mode_frame, text="",
                                                  command=self.change_appearance_mode_event,
                                                  variable=self.appearance_mode_switch_var,
                                                  onvalue="on", offvalue="off")
        self.appearance_mode_switch.grid(row=0, column=1, sticky="ew")

        # --- Frames for content ---
        self.home_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.input_output_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.artifacts_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.case_data_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")

        self.create_home_frame()
        self.create_input_output_frame()
        self.create_artifacts_frame()
        self.create_case_data_frame()

        self.select_frame_by_name("home")

    def _load_ctk_image(self, path, size, invert_for_dark=False):
        try:
            original_image = Image.open(path).resize(size, Image.Resampling.LANCZOS)
            if invert_for_dark:
                if original_image.mode == 'RGBA':
                    r, g, b, a = original_image.split()
                    rgb_image = Image.merge('RGB', (r, g, b))
                    inverted_rgb = ImageOps.invert(rgb_image)
                    inverted_image = Image.merge('RGBA', (inverted_rgb.split() + (a,)))
                else:
                    inverted_image = ImageOps.invert(original_image.convert('RGB'))
                return ctk.CTkImage(light_image=original_image, dark_image=inverted_image, size=size)
            else:
                return ctk.CTkImage(light_image=original_image, dark_image=original_image, size=size)

        except FileNotFoundError:
            print(f"Warning: Image file not found at {path}. Creating dummy image.")
            dummy_image = Image.new('RGB', size, (255, 0, 0))
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            dummy_image.save(path)
            if invert_for_dark:
                inverted_dummy_image = Image.new('RGB', size, (0, 0, 0))
                return ctk.CTkImage(light_image=dummy_image, dark_image=inverted_dummy_image, size=size)
            else:
                return ctk.CTkImage(light_image=dummy_image, dark_image=dummy_image, size=size)

    def change_appearance_mode_event(self):
        if self.appearance_mode_switch_var.get() == "on":
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")

    def handle_navigation(self, target_frame_name):
        # Validate current frame before navigating away
        if self.current_frame_name == "input_output":
            if not self.validate_input_output_and_proceed(silent=True):
                return
        elif self.current_frame_name == "artifacts":
            if not self.validate_artifacts_and_proceed(silent=True):
                return

        # If validation passes or not on a restricted frame, proceed with navigation
        self.select_frame_by_name(target_frame_name)

    def select_frame_by_name(self, name):
        # Update current_frame_name before changing selection
        self.current_frame_name = name

        self.home_button.configure(fg_color=("gray75", "gray25") if name == "home" else "transparent")
        self.input_output_button.configure(fg_color=("gray75", "gray25") if name == "input_output" else "transparent")
        self.artifacts_button.configure(fg_color=("gray75", "gray25") if name == "artifacts" else "transparent")
        self.case_data_button.configure(fg_color=("gray75", "gray25") if name == "case_data" else "transparent")

        if name == "home":
            self.home_frame.grid(row=0, column=1, sticky="nsew")
        else:
            self.home_frame.grid_forget()
        if name == "input_output":
            self.input_output_frame.grid(row=0, column=1, sticky="nsew")
        else:
            self.input_output_frame.grid_forget()
        if name == "artifacts":
            self.artifacts_frame.grid(row=0, column=1, sticky="nsew")
        else:
            self.artifacts_frame.grid_forget()
        if name == "case_data":
            self.case_data_frame.grid(row=0, column=1, sticky="nsew")
        else:
            self.case_data_frame.grid_forget()

    # --- Frame Creation Methods ---
    def create_home_frame(self):
        self.home_frame.grid_columnconfigure(0, weight=1)
        self.home_frame.grid_rowconfigure(0, weight=1)

        self.ileapp_logo_image = self._load_ctk_image("assets/icon.png", size=(225, 225), invert_for_dark=False)
        self.ileapps_logo_label = ctk.CTkLabel(self.home_frame, text="", image=self.ileapp_logo_image)
        self.ileapps_logo_label.grid(row=0, column=0, pady=(50, 10))

        self.info_frame = ctk.CTkFrame(self.home_frame, corner_radius=10, fg_color=("gray85", "gray20"))
        self.info_frame.grid(row=1, column=0, pady=20, padx=50, sticky="ew")
        self.info_frame.grid_columnconfigure(0, weight=1)

        self.home_description_label = ctk.CTkLabel(self.info_frame, text="iLEAPP v2.3 - iOS Logs, Events, And Plists Parser",
                                                    font=ctk.CTkFont(size=20, weight="bold"))
        self.home_description_label.grid(row=0, column=0, pady=(20, 5), padx=20)

        self.github_link_label = ctk.CTkLabel(self.info_frame, text="https://github.com/abrignoni/iLEAPP",
                                              font=ctk.CTkFont(size=16), text_color="blue")
        self.github_link_label.grid(row=1, column=0, pady=(5, 20), padx=20)

        self.start_button = ctk.CTkButton(self.home_frame, text="Start",
                                          font=ctk.CTkFont(size=18, weight="bold"),
                                          width=150, height=100,
                                          fg_color="#FFD700", text_color="black",
                                          hover_color="#E5C300",
                                          image=self._load_ctk_image("assets/log-in.png", size=(25,25), invert_for_dark=False),
                                          command=lambda: self.handle_navigation("input_output"))
        self.start_button.grid(row=2, column=0, pady=50)


    def create_input_output_frame(self):
        self.input_output_frame.grid_columnconfigure(0, weight=1)
        self.input_output_frame.grid_rowconfigure(7, weight=1)

        self.io_title_label = ctk.CTkLabel(self.input_output_frame, text="Input & Output",
                                                  font=ctk.CTkFont(size=24, weight="bold"),
                                                  text_color=("black", "#FFD700"))
        self.io_title_label.grid(row=0, column=0, padx=20, pady=(20, 20), sticky="w")

        self.input_label = ctk.CTkLabel(self.input_output_frame, text="Input:", font=ctk.CTkFont(size=16, weight="bold"))
        self.input_label.grid(row=1, column=0, padx=20, pady=(20, 5), sticky="w")

        self.input_entry = ctk.CTkEntry(self.input_output_frame, placeholder_text="Select input file or folder", width=400)
        self.input_entry.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")

        self.input_buttons_frame = ctk.CTkFrame(self.input_output_frame, fg_color="transparent")
        self.input_buttons_frame.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="w")
        self.input_buttons_frame.grid_columnconfigure(0, weight=0)
        self.input_buttons_frame.grid_columnconfigure(1, weight=0)

        self.input_file_button = ctk.CTkButton(self.input_buttons_frame, text="File", height=60, command=self.browse_input_file)
        self.input_file_button.grid(row=0, column=0, padx=(0, 10))

        self.input_folder_button = ctk.CTkButton(self.input_buttons_frame, text="Folder", height=60, command=self.browse_input_folder)
        self.input_folder_button.grid(row=0, column=1)

        self.output_label = ctk.CTkLabel(self.input_output_frame, text="Output Folder:", font=ctk.CTkFont(size=16, weight="bold"))
        self.output_label.grid(row=4, column=0, padx=20, pady=(10, 5), sticky="w")

        self.output_entry = ctk.CTkEntry(self.input_output_frame, placeholder_text="Select output folder", width=400)
        self.output_entry.grid(row=5, column=0, padx=20, pady=(0, 10), sticky="ew")

        self.output_folder_button = ctk.CTkButton(self.input_output_frame, text="Output Folder", height=60, command=self.browse_output_folder)
        self.output_folder_button.grid(row=6, column=0, padx=20, pady=(0, 5), sticky="w")

        self.io_error_label = ctk.CTkLabel(self.input_output_frame, text="", text_color="red")
        self.io_error_label.grid(row=7, column=0, padx=20, pady=(0, 20), sticky="w")

        self.next_io_button = ctk.CTkButton(self.input_output_frame, text="Next",
                                            font=ctk.CTkFont(size=16, weight="bold"), height=60,
                                            command=lambda: self.validate_input_output_and_proceed(silent=False))
        self.next_io_button.grid(row=8, column=0, padx=20, pady=(10, 20), sticky="se")


    def validate_input_output_and_proceed(self, silent=False):
        input_path = self.input_entry.get().strip()
        output_path = self.output_entry.get().strip()

        if not input_path and not output_path:
            self.io_error_label.configure(text="Input and Output fields are mandatory.")
            if not silent:
                messagebox.showwarning("Validation Error", "Please provide both an input and an output path to proceed.")
            return False
        elif not input_path:
            self.io_error_label.configure(text="Input field is mandatory.")
            if not silent:
                messagebox.showwarning("Validation Error", "Please provide an input path to proceed.")
            return False
        elif not output_path:
            self.io_error_label.configure(text="Output field is mandatory.")
            if not silent:
                messagebox.showwarning("Validation Error", "Please provide an output path to proceed.")
            return False
        else:
            self.io_error_label.configure(text="")
            if not silent:
                 self.select_frame_by_name("artifacts")
            return True


    def browse_input_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.input_entry.delete(0, ctk.END)
            self.input_entry.insert(0, file_path)

    def browse_input_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.input_entry.delete(0, ctk.END)
            self.input_entry.insert(0, folder_path)

    def browse_output_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.output_entry.delete(0, ctk.END)
            self.output_entry.insert(0, folder_path)

    def update_module_count_label(self):
        selected_count = 0
        total_count = len(self.artifact_list)
        for _, var in self.artifact_widgets.values():
            if var.get() == "on":
                selected_count += 1
        self.module_count_var.set(f"Number of selected modules: {selected_count} / {total_count}")


    def create_artifacts_frame(self):
        self.artifacts_frame.grid_columnconfigure(0, weight=1)
        self.artifacts_frame.grid_columnconfigure(1, weight=0)
        self.artifacts_frame.grid_columnconfigure(2, weight=0)
        self.artifacts_frame.grid_rowconfigure(4, weight=1)
        self.artifacts_frame.grid_rowconfigure(6, weight=0)

        self.artifacts_title_label = ctk.CTkLabel(self.artifacts_frame, text="Artifacts to Process",
                                                  font=ctk.CTkFont(size=24, weight="bold"),
                                                  text_color=("black", "#FFD700"))
        self.artifacts_title_label.grid(row=0, column=0, columnspan=3, padx=20, pady=(20, 20), sticky="w")

        # Added new label for module count
        self.module_count_label = ctk.CTkLabel(self.artifacts_frame, textvariable=self.module_count_var,
                                               font=ctk.CTkFont(size=16, weight="bold"),
                                               text_color=("black", "#FFD700"))
        self.module_count_label.grid(row=1, column=0, columnspan=3, padx=20, pady=(10, 5), sticky="w")

        self.search_label = ctk.CTkLabel(self.artifacts_frame, text="Search Artifacts:", font=ctk.CTkFont(size=16))
        self.search_label.grid(row=2, column=0, padx=20, pady=(20, 5), sticky="w")

        self.search_entry = ctk.CTkEntry(self.artifacts_frame, placeholder_text="Type to filter artifacts", width=200)
        self.search_entry.grid(row=3, column=0, padx=(20, 10), pady=(0, 10), sticky="ew")
        self.search_entry.bind("<KeyRelease>", self.filter_artifacts_checkboxes)

        self.select_all_button = ctk.CTkButton(self.artifacts_frame, text="Select All", height=60,
                                                command=self.select_all_artifacts)
        self.select_all_button.grid(row=3, column=1, padx=(0, 5), pady=(0, 10), sticky="e")

        self.deselect_all_button = ctk.CTkButton(self.artifacts_frame, text="Deselect All", height=60,
                                                  command=self.deselect_all_artifacts)
        self.deselect_all_button.grid(row=3, column=2, padx=(5, 20), pady=(0, 10), sticky="w")

        self.checkbox_scroll_frame = ctk.CTkScrollableFrame(self.artifacts_frame)
        self.checkbox_scroll_frame.grid(row=4, column=0, columnspan=3, padx=20, pady=20, sticky="nsew")
        self.checkbox_scroll_frame.grid_columnconfigure(0, weight=1)

        self.populate_artifacts_checkboxes()

        self.artifacts_error_label = ctk.CTkLabel(self.artifacts_frame, text="", text_color="red")
        self.artifacts_error_label.grid(row=5, column=0, columnspan=3, padx=20, pady=5, sticky="ew")

        self.artifacts_bottom_buttons_frame = ctk.CTkFrame(self.artifacts_frame, fg_color="transparent")
        self.artifacts_bottom_buttons_frame.grid(row=6, column=0, columnspan=3, padx=20, pady=(20, 20), sticky="ew")
        self.artifacts_bottom_buttons_frame.grid_columnconfigure(0, weight=0)
        self.artifacts_bottom_buttons_frame.grid_columnconfigure(1, weight=0)
        self.artifacts_bottom_buttons_frame.grid_columnconfigure(2, weight=1)

        self.load_profile_button = ctk.CTkButton(self.artifacts_bottom_buttons_frame, text="Load Profile", height=60,
                                                 command=self.load_profile)
        self.load_profile_button.grid(row=0, column=0, padx=(0, 10), sticky="w")

        self.save_profile_button = ctk.CTkButton(self.artifacts_bottom_buttons_frame, text="Save Profile", height=60,
                                                 command=self.save_profile)
        self.save_profile_button.grid(row=0, column=1, padx=(0, 10), sticky="w")

        self.next_artifacts_button = ctk.CTkButton(self.artifacts_bottom_buttons_frame, text="Next",
                                                   font=ctk.CTkFont(size=16, weight="bold"), height=60,
                                                   command=lambda: self.validate_artifacts_and_proceed(silent=False))
        self.next_artifacts_button.grid(row=0, column=2, padx=(10, 0), sticky="e")
        self.update_module_count_label()


    def populate_artifacts_checkboxes(self):
        for widget in self.checkbox_scroll_frame.winfo_children():
            widget.destroy()
        self.artifact_widgets = {}

        for i, artifact in enumerate(self.artifact_list):
            var = ctk.StringVar(value="on")
            checkbox = ctk.CTkCheckBox(master=self.checkbox_scroll_frame, text=artifact, variable=var, onvalue="on", offvalue="off", command=self.update_module_count_label)
            checkbox.grid(row=i, column=0, pady=(5, 5), padx=10, sticky="w")
            self.artifact_widgets[artifact] = (checkbox, var)
        self.update_module_count_label()

    def filter_artifacts_checkboxes(self, event=None):
        search_term = self.search_entry.get().strip().lower()
        current_row = 0

        for artifact_name in self.artifact_list:
            checkbox_widget, var = self.artifact_widgets[artifact_name]

            if search_term in artifact_name.lower():
                checkbox_widget.grid(row=current_row, column=0, pady=(5, 5), padx=10, sticky="w")
                current_row += 1
            else:
                checkbox_widget.grid_forget()

    def select_all_artifacts(self):
        for artifact_name in self.artifact_list:
            _, var = self.artifact_widgets[artifact_name]
            var.set("on")
        self.filter_artifacts_checkboxes()
        self.update_module_count_label()

    def deselect_all_artifacts(self):
        for artifact_name in self.artifact_list:
            _, var = self.artifact_widgets[artifact_name]
            var.set("off")
        self.filter_artifacts_checkboxes()
        self.update_module_count_label()

    def load_profile(self):
        file_path = filedialog.askopenfilename(filetypes=[('iLEAPP Profile', '*.ilprofile'),])
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    profile_data = json.load(f)
                for artifact_name, state in profile_data.items():
                    if artifact_name in self.artifact_widgets:
                        _, var = self.artifact_widgets[artifact_name]
                        var.set("on" if state else "off")
                messagebox.showinfo("Profile Loaded", f"Profile loaded successfully from {os.path.basename(file_path)}")
                self.filter_artifacts_checkboxes()
                self.update_module_count_label()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load profile: {e}")

    def save_profile(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[('iLEAPP Profile', '*.ilprofile'),])
        if file_path:
            profile_data = {}
            for artifact_name in self.artifact_list:
                _, var = self.artifact_widgets[artifact_name]
                profile_data[artifact_name] = (var.get() == "on")
            try:
                with open(file_path, 'w') as f:
                    json.dump(profile_data, f, indent=4)
                messagebox.showinfo("Profile Saved", f"Profile saved successfully to {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save profile: {e}")
    
    
    def save_case_data(self):
        file_path = filedialog.asksaveasfilename(title='Save a case data file', defaultextension=".lcasedata", filetypes=[('LEAPP Case Data', '*.lcasedata'),])
        if file_path:
            # Create a dictionary of the string variable values
            case_data_values = {key: value.get() for key, value in self.casedata.items()}
            
            # Create the main dictionary with the required structure
            case_data_dict = {'leapp': 'case_data', 'case_data_values': case_data_values}
            
            try:
                with open(file_path, 'wt', encoding='utf-8') as case_data_out:
                    json.dump(case_data_dict, case_data_out, indent=4)
                messagebox.showinfo("Case Data Saved", f"Case data saved successfully to {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save case data: {e}")


    def validate_artifacts_and_proceed(self, silent=False):
        any_checked = False
        for artifact_name in self.artifact_list:
            _, var = self.artifact_widgets[artifact_name]
            if var.get() == "on":
                any_checked = True
                break

        if not any_checked:
            self.artifacts_error_label.configure(text="At least one artifact must be selected to proceed.")
            if not silent:
                messagebox.showwarning("Validation Error", "Please select at least one artifact to process.")
            return False
        else:
            self.artifacts_error_label.configure(text="")
            if not silent:
                self.select_frame_by_name("case_data")
            return True


    def create_case_data_frame(self):
        self.case_data_frame.grid_columnconfigure(0, weight=1)
        self.case_data_frame.grid_rowconfigure(4, weight=1)

        self.case_data_title_label = ctk.CTkLabel(self.case_data_frame, text="Add Case Data (Optional)",
                                                  font=ctk.CTkFont(size=24, weight="bold"),
                                                  text_color=("black", "#FFD700"))
        self.case_data_title_label.grid(row=0, column=0, padx=20, pady=(20, 20), sticky="w")

        # --- Case Number Frame ---
        self.case_number_frame = ctk.CTkFrame(self.case_data_frame, corner_radius=10, fg_color=("gray85", "gray20"))
        self.case_number_frame.grid(row=1, column=0, padx=20, pady=(10, 10), sticky="ew")
        self.case_number_frame.grid_columnconfigure(0, weight=1)

        self.case_number_label = ctk.CTkLabel(self.case_number_frame, text="Case Number", font=ctk.CTkFont(size=14, weight="bold"))
        self.case_number_label.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")
        self.case_number_entry = ctk.CTkEntry(self.case_number_frame, placeholder_text="", width=300, textvariable=self.casedata['Case Number'])
        self.case_number_entry.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="ew")

        # --- Agency Frame ---
        self.agency_frame = ctk.CTkFrame(self.case_data_frame, corner_radius=10, fg_color=("gray85", "gray20"))
        self.agency_frame.grid(row=2, column=0, padx=20, pady=(10, 10), sticky="ew")
        self.agency_frame.grid_columnconfigure(0, weight=1)

        self.agency_name_label = ctk.CTkLabel(self.agency_frame, text="Agency", font=ctk.CTkFont(size=14, weight="bold"))
        self.agency_name_label.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")
        self.agency_name_entry = ctk.CTkEntry(self.agency_frame, placeholder_text="", width=300, textvariable=self.casedata['Agency'])
        self.agency_name_entry.grid(row=1, column=0, padx=15, pady=(0, 5), sticky="ew")

        self.agency_logo_label = ctk.CTkLabel(self.agency_frame, text="Logo", font=ctk.CTkFont(size=14))
        self.agency_logo_label.grid(row=2, column=0, padx=15, pady=(5, 5), sticky="w")

        self.agency_logo_control_frame = ctk.CTkFrame(self.agency_frame, fg_color="transparent")
        self.agency_logo_control_frame.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="ew")
        self.agency_logo_control_frame.grid_columnconfigure(0, weight=1)
        self.agency_logo_control_frame.grid_columnconfigure(1, weight=0)

        self.agency_logo_entry = ctk.CTkEntry(self.agency_logo_control_frame, placeholder_text="", textvariable=self.casedata['Agency Logo Path'])
        self.agency_logo_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.agency_logo_button = ctk.CTkButton(self.agency_logo_control_frame, text="Add File", height=60, command=self.browse_agency_logo)
        self.agency_logo_button.grid(row=0, column=1, sticky="e")

        # --- Examiner Frame ---
        self.examiner_frame = ctk.CTkFrame(self.case_data_frame, corner_radius=10, fg_color=("gray85", "gray20"))
        self.examiner_frame.grid(row=3, column=0, padx=20, pady=(10, 10), sticky="ew")
        self.examiner_frame.grid_columnconfigure(0, weight=1)

        self.examiner_label = ctk.CTkLabel(self.examiner_frame, text="Examiner", font=ctk.CTkFont(size=14, weight="bold"))
        self.examiner_label.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")
        self.examiner_entry = ctk.CTkEntry(self.examiner_frame, placeholder_text="", width=300, textvariable=self.casedata['Examiner'])
        self.examiner_entry.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="ew")

        # --- Action Buttons Frame ---
        self.case_data_buttons_frame = ctk.CTkFrame(self.case_data_frame, fg_color="transparent")
        self.case_data_buttons_frame.grid(row=5, column=0, padx=20, pady=(12, 28), sticky="sew")
        self.case_data_buttons_frame.grid_columnconfigure(0, weight=0)
        self.case_data_buttons_frame.grid_columnconfigure(1, weight=0)
        self.case_data_buttons_frame.grid_columnconfigure(2, weight=1)
        self.case_data_buttons_frame.grid_columnconfigure(3, weight=0)
        self.case_data_buttons_frame.grid_columnconfigure(4, weight=0)

        self.load_case_data_button = ctk.CTkButton(self.case_data_buttons_frame, text="Load Case Data File", height=60, command=self.load_case_data)
        self.load_case_data_button.grid(row=0, column=0, padx=(0, 10), sticky="w")

        self.save_case_data_button = ctk.CTkButton(self.case_data_buttons_frame, text="Save Case Data File", height=60, command=self.save_case_data)
        self.save_case_data_button.grid(row=0, column=1, padx=(0, 10), sticky="w")

        self.separator_label = ctk.CTkLabel(self.case_data_buttons_frame, text="|", font=ctk.CTkFont(size=24), text_color=("gray50", "gray40"))
        self.separator_label.grid(row=0, column=2, padx=(5, 5), sticky="ns")

        self.clear_button = ctk.CTkButton(self.case_data_buttons_frame, text="Clear", fg_color="#FFD700", text_color="black", hover_color="#E5C300", height=60, command=self.clear_case_data_fields)
        self.clear_button.grid(row=0, column=3, padx=(10, 5), sticky="e")

        self.close_button = ctk.CTkButton(self.case_data_buttons_frame, text="Process",
                                          font=ctk.CTkFont(size=16, weight="bold"), height=60,
                                          command=self.destroy)
        self.close_button.grid(row=0, column=4, padx=(5, 0), sticky="e")

    def browse_agency_logo(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif *.bmp")])
        if file_path:
            self.agency_logo_entry.delete(0, ctk.END)
            self.agency_logo_entry.insert(0, file_path)

    def clear_case_data_fields(self):
        # Clear the variables, which will also clear the entry widgets
        for var in self.casedata.values():
            var.set("")
        messagebox.showinfo("Clear Fields", "All Case Data fields have been cleared.")
    
    def load_case_data(self):
        file_path = filedialog.askopenfilename(title='Load a case data file', defaultextension=".lcasedata", filetypes=[('LEAPP Case Data', '*.lcasedata'),])
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as case_data_in:
                    loaded_data = json.load(case_data_in)
                    case_data_values = loaded_data.get('case_data_values', {})
                    for key, value in case_data_values.items():
                        if key in self.casedata:
                            self.casedata[key].set(value)
                messagebox.showinfo("Case Data Loaded", f"Case data loaded successfully from {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load case data: {e}")

if __name__ == "__main__":
    app = App()
    app.mainloop()