#!/usr/bin/env python3

import tkinter as tk
import customtkinter as ctk
import typing
import json
import queue
import threading
import traceback
import ileapp
import webbrowser
import base64
import os
import sys
from pathlib import Path

import scripts.plugin_loader as plugin_loader
import leapp_functions.app.history as history

from PIL import Image, ImageTk
from tkinter import filedialog as tk_filedialog, messagebox as tk_msgbox
from scripts.version_info import leapp_name, leapp_version, check_runtime_dependencies
from scripts.search_files import *
from scripts.raw_image import (RAW_IMAGE_LABEL, RAW_IMAGE_SUFFIXES, RAW_IMAGE_FILE_PATTERNS,
                               names_an_image_folder, ask_image_keys)
from scripts.ilapfuncs import *
from scripts.tz_offset import tzvalues
from scripts.modules_to_exclude import modules_to_exclude
from scripts.lavafuncs import *
from leapp_functions.lava_launcher import (
    LAVA_WEBSITE,
    find_lava_launcher,
    open_lava_project,
    open_output_folder,
)
from leapp_functions.app.platform import sanitize_file_name
from leapp_functions.app.output import default_output_folder_name, validate_output_folder_available
from scripts.context import Context
from scripts.lavafuncs import lava_json_name


CRUNCH_POLL_MS = 50
RADIUS = 6
BORDER_WIDTH = 1

# --- Global Color Variables (Light Mode, Dark Mode) ---
WIDGET_COLOR = ("#e0e5eb", "#222a33")
WIDGET_HOVER = ("#c9d1d9", "#2e3945")
BORDER_COLOR = ("#b0b9c4", "#5c6a7a")
APP_BG_COLOR = ("#f0f2f5", "#171b21")
FRAME_BG_COLOR = ("#ffffff", "#0f1317")
TEXT_COLOR = ("#111820", "#9da1a7")
CHECKMARK_COLOR = ("#000000", "#ffffff")

# Setup CustomTkinter Default Theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def create_labelframe(parent, text):
    """Helper to mimic ttk.LabelFrame using rounded CTkFrames."""
    outer_frame = ctk.CTkFrame(
        parent, corner_radius=RADIUS, border_width=BORDER_WIDTH, 
        border_color=BORDER_COLOR, fg_color=APP_BG_COLOR
    )
    lbl = ctk.CTkLabel(outer_frame, text=text, font=("Helvetica", 12, "bold"), text_color=TEXT_COLOR)
    lbl.pack(anchor='w', padx=10, pady=(5, 0))
    inner_frame = ctk.CTkFrame(outer_frame, fg_color=FRAME_BG_COLOR, corner_radius=RADIUS)
    inner_frame.pack(fill='both', expand=True, padx=5, pady=5)
    return outer_frame, inner_frame


def allow_output_folder_name_chars(proposed):
    return sanitize_file_name(proposed) == proposed


def show_history_menu(button, path_type):
    menu = tk.Menu(main_window, tearoff=0)

    if not history.is_history_enabled():
        menu.add_command(label="(History Disabled - Enable in Settings)", state="disabled")
    else:
        paths = history.get_input_paths() if path_type == 'input' else history.get_output_paths()
        if not paths:
            menu.add_command(label="(No recent paths)", state="disabled")
        for path in paths:
            def set_path(p=path):
                if path_type == 'input':
                    input_entry.delete(0, tk.END)
                    input_entry.insert(0, p)
                else:
                    output_entry.delete(0, tk.END)
                    output_entry.insert(0, p)
            menu.add_command(label=history.format_path_for_display(path), command=set_path)
    x = input_entry.winfo_rootx()
    y = button.winfo_rooty() + button.winfo_height()
    menu.post(x, y)


def pickModules():
    global mlist
    for plugin in sorted(loader.plugins, key=lambda p: p.category.upper()):
        if (plugin.module_name == 'iTunesBackupInfo'
                or plugin.name == 'last_build'
                or plugin.module_name == 'logarchive' and plugin.name != 'logarchive'):
            continue
        plugin_enabled = tk.BooleanVar(value=False) if plugin.module_name in modules_to_exclude else tk.BooleanVar(value=True)
        plugin_module_name = plugin.artifact_info.get('name', plugin.name) if hasattr(plugin, 'artifact_info') else plugin.name
        mlist[plugin.name] = [plugin.category, plugin_module_name, plugin.module_name, plugin_enabled]


def get_selected_modules():
    selected_modules = []
    for artifact_name, module_infos in mlist.items():
        # Index 3 holds the tk.BooleanVar state
        if module_infos[3].get():
            selected_modules.append(artifact_name)
    selected_modules_label.configure(text=f'Number of selected modules: {len(selected_modules)} / {len(mlist)}')
    return selected_modules


def module_matches_filter(module_infos, filter_term=None):
    if filter_term is None:
        filter_term = modules_filter_var.get().lower()
    return filter_term in f"{module_infos[0]} {module_infos[1]}".lower()


def select_all():
    for module_infos in mlist.values():
        if module_matches_filter(module_infos):
            module_infos[3].set(True)
    get_selected_modules()


def deselect_all():
    for module_infos in mlist.values():
        if module_matches_filter(module_infos):
            module_infos[3].set(False)
    get_selected_modules()


def filter_modules(*args):
    """Instantly hide or show pre-loaded checkboxes while maintaining alphabetical order."""
    filter_term = modules_filter_var.get().lower()

    for artifact_name, module_infos in mlist.items():
        if len(module_infos) > 4:
            cb = module_infos[4]
            # Remove from layout first to clear the current packing order
            cb.pack_forget()
            
            # Repack only if it matches. Because the mlist dictionary 
            # maintains its alphabetical order, they pack sequentially.
            if module_matches_filter(module_infos, filter_term):
                cb.pack(anchor='w', pady=2, padx=5)


def load_profile():
    global profile_filename
    destination_path = tk_filedialog.askopenfilename(parent=main_window,
                                                     title='Load a profile',
                                                     filetypes=(('iLEAPP Profile', '*.ilprofile'),))
    if destination_path and os.path.exists(destination_path):
        profile_load_error = None
        with open(destination_path, 'rt', encoding='utf-8') as profile_in:
            try:
                profile = json.load(profile_in)
            except:
                profile_load_error = 'File was not a valid profile file: invalid format'
        if not profile_load_error:
            if isinstance(profile, dict):
                if profile.get('leapp') != 'ileapp' or profile.get('format_version') != 1:
                    profile_load_error = 'File was not a valid profile file: incorrect LEAPP or version'
                else:
                    deselect_all()
                    ticked = set(profile.get('plugins', []))
                    for artifact_name, module_infos in mlist.items():
                        if artifact_name in ticked:
                            module_infos[3].set(True)
                    get_selected_modules()
            else:
                profile_load_error = 'File was not a valid profile file: invalid format'
        if profile_load_error:
            tk_msgbox.showerror(title='Error', message=profile_load_error, parent=main_window)
        else:
            profile_filename = destination_path
            tk_msgbox.showinfo(
                title='Profile loaded', message=f'Loaded profile: {destination_path}', parent=main_window)


def save_profile():
    destination_path = tk_filedialog.asksaveasfilename(parent=main_window,
                                                       title='Save a profile',
                                                       filetypes=(('iLEAPP Profile', '*.ilprofile'),),
                                                       defaultextension='.ilprofile')
    if destination_path:
        selected_modules = get_selected_modules()
        with open(destination_path, 'wt', encoding='utf-8') as profile_out:
            json.dump({'leapp': 'ileapp', 'format_version': 1, 'plugins': selected_modules}, profile_out)
        tk_msgbox.showinfo(
            title='Save a profile', message=f'Profile saved: {destination_path}', parent=main_window)


def ValidateInput():
    i_path = input_entry.get()
    o_path = output_entry.get()
    ext_type = ''

    if len(i_path) == 0:
        tk_msgbox.showerror(title='Error', message='No INPUT file or folder selected!', parent=main_window)
        return False, ext_type, None
    elif not os.path.exists(i_path):
        tk_msgbox.showerror(title='Error', message='INPUT file/folder does not exist!', parent=main_window)
        return False, ext_type, None
    elif names_an_image_folder(i_path):
        ext_type = 'raw'
    elif os.path.isdir(i_path):
        itunes_backup_type = get_itunes_backup_type(i_path)
        if itunes_backup_type:
            supported, encrypted, message = check_itunes_backup_status(
                i_path, itunes_backup_type)
            if not supported:
                tk_msgbox.showerror(title='Error', message=message, parent=main_window)
                return False, ext_type, None
            else:
                if encrypted:
                    decryption_keys = None
                    while not decryption_keys:
                        password = tk.simpledialog.askstring(
                            "Detected encrypted iTunes backup",
                            "iTunes Backup password:",
                            show='*',
                            parent=main_window)
                        decryption_keys, message = decrypt_itunes_backup(i_path, password)
                        if not decryption_keys:
                            tk_msgbox.showerror(title='Error', message=message, parent=main_window)
                            return False, ext_type, decryption_keys
                        else:
                            return True, 'itunes', decryption_keys
            ext_type = 'itunes'
        else:
            ext_type = 'fs'
    else:
        ext_type = Path(i_path).suffix[1:].lower()
        if ext_type in RAW_IMAGE_SUFFIXES:
            ext_type = 'raw'
        elif i_path.lower().endswith('.tar.xz'):
            ext_type = 'tar'

    if len(o_path) == 0:
        tk_msgbox.showerror(title='Error', message='No output path provided!', parent=main_window)
        return False, ext_type, None

    folder_name = output_folder_name_entry.get().strip()
    if not folder_name:
        tk_msgbox.showerror(title='Error', message='Output folder name cannot be empty!', parent=main_window)
        return False, ext_type, None
    folder_name_valid, folder_name_error = validate_output_folder_available(o_path, folder_name)
    if not folder_name_valid:
        tk_msgbox.showerror(title='Error', message=folder_name_error, parent=main_window)
        return False, ext_type, None

    if len(get_selected_modules()) == 0:
        tk_msgbox.showerror(title='Error', message='No module selected for processing!', parent=main_window)
        return False, ext_type, None

    return True, ext_type, None


def open_report(report_path):
    webbrowser.open_new_tab('file://' + report_path)
    main_window.quit()


def open_lava(project_path, launcher):
    try:
        open_lava_project(project_path, launcher, logfunc)
    except (OSError, ValueError) as ex:
        tk_msgbox.showerror(
            title='Unable to open LAVA',
            message=f'iLEAPP could not open the project in LAVA:\n{ex}',
            parent=main_window)
        return
    main_window.quit()


def explore_lava():
    webbrowser.open_new_tab(LAVA_WEBSITE)


def open_folder(output_path):
    try:
        open_output_folder(output_path)
    except OSError as ex:
        tk_msgbox.showerror(
            title='Unable to open output folder',
            message=f'iLEAPP could not open the output folder:\n{ex}',
            parent=main_window)


def open_website(url):
    webbrowser.open_new_tab(url)


def open_settings_window():
    settings_window = ctk.CTkToplevel(main_window)
    settings_window.transient(main_window)
    settings_window.configure(fg_color=APP_BG_COLOR)
    settings_window_width = 400
    settings_window_height = 340

    main_window.update_idletasks()
    main_x = main_window.winfo_x()
    main_y = main_window.winfo_y()
    main_w = main_window.winfo_width()
    main_h = main_window.winfo_height()

    margin_width = main_x + (main_w - settings_window_width) // 2
    margin_height = main_y + (main_h - settings_window_height) // 2

    settings_window.geometry(f'{settings_window_width}x{settings_window_height}+{margin_width}+{margin_height}')
    settings_window.resizable(False, False)
    settings_window.title('Settings')

    def close_settings_window():
        settings_window.destroy()

    settings_window.protocol("WM_DELETE_WINDOW", close_settings_window)

    settings_title_label = ctk.CTkLabel(settings_window, text='Settings', font=('Helvetica', 18, 'bold'), text_color=TEXT_COLOR)
    settings_title_label.grid(row=0, column=0, padx=14, pady=7, sticky='w')

    appearance_label = ctk.CTkLabel(settings_window, text="Appearance Mode:", font=('Helvetica', 14), text_color=TEXT_COLOR)
    appearance_label.grid(row=1, column=0, padx=14, pady=(10, 0), sticky='w')

    appearance_segmented = ctk.CTkSegmentedButton(
        settings_window, values=["Dark", "Light", "System"],
        command=lambda mode: ctk.set_appearance_mode(mode),
        fg_color=BORDER_COLOR, selected_color=WIDGET_COLOR,
        selected_hover_color=WIDGET_HOVER, text_color=TEXT_COLOR
    )
    appearance_segmented.grid(row=2, column=0, padx=14, pady=(5, 10), sticky='w')
    
    current_mode = ctk.get_appearance_mode().capitalize()
    if current_mode in ["Dark", "Light", "System"]:
        appearance_segmented.set(current_mode)
    else:
        appearance_segmented.set("System")

    history_enabled_var = tk.BooleanVar(value=history.is_history_enabled())

    def toggle_history():
        history.set_history_enabled(history_enabled_var.get())

    def update_clear_history_button():
        state = tk.NORMAL if history.has_history() else tk.DISABLED
        clear_history_btn.configure(state=state)

    def open_clear_history_window():
        clear_window = ctk.CTkToplevel(settings_window)
        clear_window.transient(settings_window)
        clear_window.configure(fg_color=APP_BG_COLOR)
        clear_window_width = 460
        clear_window_height = 220

        settings_window.update_idletasks()
        settings_x = settings_window.winfo_x()
        settings_y = settings_window.winfo_y()
        settings_w = settings_window.winfo_width()
        settings_h = settings_window.winfo_height()

        margin_width = settings_x + (settings_w - clear_window_width) // 2
        margin_height = settings_y + (settings_h - clear_window_height) // 2

        clear_window.geometry(f'{clear_window_width}x{clear_window_height}+{margin_width}+{margin_height}')
        clear_window.resizable(False, False)
        clear_window.title('Clear History')

        def close_clear_window():
            clear_window.destroy()

        clear_window.protocol("WM_DELETE_WINDOW", close_clear_window)

        clear_title_label = ctk.CTkLabel(clear_window, text='Clear History', font=('Helvetica', 18, 'bold'), text_color=TEXT_COLOR)
        clear_title_label.grid(row=0, column=0, padx=14, pady=7, sticky='w')

        clear_message = (
            'History is stored in shared LEAPP files. Input and output paths are shared by all '
            'LEAPP tools, while recent runs are tagged by tool.'
        )
        clear_message_label = ctk.CTkLabel(clear_window, text=clear_message, wraplength=420, text_color=TEXT_COLOR)
        clear_message_label.grid(row=1, column=0, padx=14, pady=10, sticky='w')

        button_frame = ctk.CTkFrame(clear_window, fg_color="transparent", corner_radius=RADIUS)
        button_frame.grid(row=2, column=0, padx=14, pady=18, sticky='e')

        def clear_single_leapp_history():
            if not tk_msgbox.askyesno(
                    title=f'Clear {leapp_name} history',
                    message=(f'Clear shared recent input/output paths and '
                             f'{leapp_name} recent run entries?'),
                    parent=clear_window):
                return
            history.clear_single_leapp_history(leapp_name.lower())
            update_clear_history_button()
            close_clear_window()

        def clear_all_history():
            if not tk_msgbox.askyesno(
                    title='Clear all LEAPP history',
                    message='Clear all shared LEAPP history?',
                    parent=clear_window):
                return
            history.clear_history()
            update_clear_history_button()
            close_clear_window()

        clear_single_leapp_btn = ctk.CTkButton(
            button_frame, text=f'Clear {leapp_name} History',
            command=clear_single_leapp_history,
            corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
            fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
        clear_single_leapp_btn.pack(side='left', padx=5)
        if not history.has_single_leapp_history(leapp_name.lower()):
            clear_single_leapp_btn.configure(state=tk.DISABLED)

        clear_all_btn = ctk.CTkButton(
            button_frame, text='Clear All History',
            command=clear_all_history,
            corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
            fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
        clear_all_btn.pack(side='left', padx=5)

        cancel_btn = ctk.CTkButton(
            button_frame, text='Cancel', command=close_clear_window,
            corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
            fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
        cancel_btn.pack(side='left', padx=5)

    history_check = ctk.CTkCheckBox(
        settings_window, text='Enable saving paths as recent history',
        variable=history_enabled_var, command=toggle_history,
        corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
        fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR,
        checkmark_color=CHECKMARK_COLOR
    )
    history_check.grid(row=3, column=0, padx=14, pady=20, sticky='w')

    clear_history_btn = ctk.CTkButton(
        settings_window, text='Clear History',
        command=open_clear_history_window,
        corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
        fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
    clear_history_btn.grid(row=4, column=0, padx=14, pady=10, sticky='w')
    update_clear_history_button()

    close_btn = ctk.CTkButton(
        settings_window, text='Close', command=close_settings_window,
        corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
        fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
    close_btn.grid(row=5, column=0, padx=14, pady=20, sticky='e')


def resource_path(filename):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, 'assets', filename)


def process(casedata):
    is_valid, extracttype, decryption_keys = ValidateInput()

    if is_valid:
        image_password = None
        if extracttype == 'raw':
            image_password = ask_image_keys(main_window, input_entry.get())
            if image_password is None:
                return
        GuiWindow.window_handle = main_window
        input_path = input_entry.get()
        output_folder = output_entry.get()

        if is_platform_windows():
            if input_path[1] == ':' and extracttype == 'fs': input_path = '\\\\?\\' + input_path.replace('/', '\\')
            if output_folder[1] == ':': output_folder = '\\\\?\\' + output_folder.replace('/', '\\')

        selected_modules = get_selected_modules()
        selected_modules = [loader[module] for module in selected_modules]
        
        # Determine internal Max Value for CTkProgressBar
        progress_bar._maximum_val = len(selected_modules)
        progress_bar.set(0)

        casedata = {key: value.get() for key, value in casedata.items()}
        out_params = OutputParameters(output_folder, output_folder_name_entry.get().strip())
        Context.set_output_params(out_params)
        keychain_path = keychain_entry.get().strip()
        if keychain_path and not os.path.isfile(keychain_path):
            tk_msgbox.showerror(title='Error',
                                message=f'Keychain file not found:\n{keychain_path}',
                                parent=main_window)
            return
        Context.set_keychain_path(keychain_path or None)
        wrap_text = True
        time_offset = timezone_set.get()
        if time_offset == '':
            time_offset = 'UTC'

        bottom_frame.pack_forget()
        mlist_frame_outer.pack_forget()
        output_frame_outer.pack_forget()
        input_frame_outer.pack_forget()
        keychain_frame_outer.pack_forget()
        logtext_frame.pack(padx=8, pady=4, expand=True, fill='both')
        progress_bar_frame.pack(side='bottom', padx=2, pady=2, ipady=2, fill='x', before=logtext_frame)

        history.record_input_path(input_path)
        history.record_output_path(output_folder)

        GuiWindow.message_queue = queue.Queue()
        worker = threading.Thread(
            target=run_crunch,
            args=(GuiWindow.message_queue, selected_modules, extracttype, input_path,
                  out_params, wrap_text, casedata, time_offset, decryption_keys,
                  image_password),
            daemon=True)
        worker.start()
        main_window.after(CRUNCH_POLL_MS, poll_crunch, GuiWindow.message_queue, out_params)


def run_crunch(message_queue, selected_modules, extracttype, input_path, out_params, wrap_text,
               case_info, time_offset, decryption_keys, image_password=None):
    try:
        initialize_lava(input_path, out_params.output_folder_base, extracttype, profile_filename)
        crunch_successful = ileapp.crunch_artifacts(
            selected_modules, extracttype, input_path, out_params, wrap_text,
            loader, case_info, time_offset, profile_filename, None, decryption_keys,
            image_password=image_password)
        lava_finalize_output(out_params.output_folder_base)
    except Exception:
        message_queue.put(('failed', traceback.format_exc()))
    else:
        message_queue.put(('done', crunch_successful))


def poll_crunch(message_queue, out_params):
    pending_logs = []
    finished = None
    while finished is None:
        try:
            kind, payload = message_queue.get_nowait()
        except queue.Empty:
            break
        if kind == 'log':
            pending_logs.append(payload)
        elif kind == 'progress':
            # CTkProgressBar utilizes floats from 0.0 to 1.0
            if hasattr(progress_bar, '_maximum_val') and progress_bar._maximum_val > 0:
                progress_bar.set(payload / progress_bar._maximum_val)
        else:
            finished = (kind, payload)

    if pending_logs:
        log_text.insert('end', ''.join(pending_logs))
        log_text.see('end')

    if finished is None:
        main_window.after(CRUNCH_POLL_MS, poll_crunch, message_queue, out_params)
        return

    GuiWindow.end_worker_run()
    kind, payload = finished
    if kind == 'failed':
        logfunc('Processing failed with an unhandled error:')
        logfunc(payload)
        finish_crunch(False, out_params)
    else:
        finish_crunch(payload, out_params)


def finish_crunch(crunch_successful, out_params):
    if crunch_successful:
        report_path = os.path.join(out_params.output_folder_base, 'index.html')
        lava_project_path = os.path.join(out_params.output_folder_base, lava_json_name)
        history.record_recent_run(leapp_name.lower(), leapp_version, lava_project_path)

        output_folder_path = out_params.output_folder_base
        if report_path.startswith('\\\\?\\'):
            report_path = report_path[4:]
            lava_project_path = lava_project_path[4:]
            output_folder_path = output_folder_path[4:]
        if report_path.startswith('\\\\'):
            report_path = report_path[2:]
            lava_project_path = lava_project_path[2:]
            output_folder_path = output_folder_path[2:]
        if lava_only_artifacts:
            message = "You have selected artifacts that are likely to return too much data "
            message += "to be viewed in a Web browser.\n\n"
            message += "Please see the 'LAVA only artifacts' tab in the HTML report for a list of these artifacts "
            message += "and instructions on how to view them."
            tk_msgbox.showwarning(title="Important information", message=message, parent=main_window)
        
        progress_bar.pack_forget()
        completion_button_frame = ctk.CTkFrame(progress_bar_frame, fg_color="transparent", corner_radius=RADIUS)
        completion_button_frame.place(relx=0.5, rely=0.5, anchor='center')
        open_report_button = ctk.CTkButton(
            completion_button_frame, text='Open HTML in Browser & Close',
            command=lambda: open_report(report_path),
            corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
            fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
        open_report_button.pack(side='left', padx=5)

        lava_launcher = find_lava_launcher(lava_project_path)
        if lava_launcher:
            lava_button = ctk.CTkButton(
                completion_button_frame, text='Open Project in LAVA & Close',
                command=lambda: open_lava(lava_project_path, lava_launcher),
                corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
                fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
        else:
            lava_button = ctk.CTkButton(
                completion_button_frame, text='Explore LAVA',
                command=explore_lava,
                corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
                fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
        lava_button.pack(side='left', padx=5)

        open_folder_button = ctk.CTkButton(
            completion_button_frame, text='Open Output Folder',
            command=lambda: open_folder(output_folder_path),
            corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
            fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
        open_folder_button.pack(side='left', padx=5)
    else:
        log_path = out_params.screen_output_file_path
        if log_path.startswith('\\\\?\\'):
            log_path = log_path[4:]
        tk_msgbox.showerror(
            title='Error',
            message=f'Processing failed  :( \nSee log for error details..\nLog file located at {log_path}',
            parent=main_window)


def close_main_window():
    if GuiWindow.message_queue is not None:
        close_anyway = tk_msgbox.askokcancel(
            title='Processing still running',
            message='A run is still in progress.\n\nClosing now stops it where it is.\nClose anyway?',
            icon=tk_msgbox.WARNING,
            default=tk_msgbox.CANCEL,
            parent=main_window)
        if not close_anyway:
            return
    main_window.quit()


def select_input(button_type):
    if button_type == 'file':
        input_filename = tk_filedialog.askopenfilename(parent=main_window,
                                                       title='Select a file',
                                                       filetypes=(('All supported files',
                                                                   '*.tar *.zip *.gz *.xz ' + RAW_IMAGE_FILE_PATTERNS),
                                                                  ('tar file', '*.tar'), ('zip file', '*.zip'),
                                                                  ('gz file', '*.gz'),
                                                                  ('tar.xz file', '*.xz'),
                                                                  (RAW_IMAGE_LABEL, RAW_IMAGE_FILE_PATTERNS)))
    else:
        input_filename = tk_filedialog.askdirectory(parent=main_window, title='Select a folder')
    input_entry.delete(0, 'end')
    input_entry.insert(0, input_filename)
    if input_filename:
        history.record_input_path(input_filename)


def select_keychain():
    keychain_filename = tk_filedialog.askopenfilename(
        parent=main_window,
        title='Select a keychain file',
        filetypes=(('Keychain files', '*.plist *.xml'), ('All files', '*.*')))
    if keychain_filename:
        keychain_entry.delete(0, 'end')
        keychain_entry.insert(0, keychain_filename)


def clear_keychain():
    keychain_entry.delete(0, 'end')


def select_output():
    output_filename = tk_filedialog.askdirectory(parent=main_window, title='Select a folder')
    output_entry.delete(0, 'end')
    output_entry.insert(0, output_filename)
    if output_filename:
        history.record_output_path(output_filename)


def case_data():
    global casedata

    def clear():
        case_number_entry.delete(0, 'end')
        case_agency_name_entry.delete(0, 'end')
        case_agency_logo_path_entry.delete(0, 'end')
        case_agency_logo_mimetype.delete(0, 'end')
        case_agency_logo_b64.delete(0, 'end')
        case_examiner_entry.delete(0, 'end')

    def save_case():
        destination_path = tk_filedialog.asksaveasfilename(parent=case_window,
                                                           title='Save a case data file',
                                                           filetypes=(('LEAPP Case Data', '*.lcasedata'),),
                                                           defaultextension='.lcasedata')
        if destination_path:
            json_casedata = {key: value.get() for key, value in casedata.items()}
            with open(destination_path, 'wt', encoding='utf-8') as case_data_out:
                json.dump({'leapp': 'case_data', 'case_data_values': json_casedata}, case_data_out)
            tk_msgbox.showinfo(
                title='Save Case Data', message=f'Case Data saved: {destination_path}', parent=case_window)

    def load_case():
        destination_path = tk_filedialog.askopenfilename(parent=case_window,
                                                         title='Load case data',
                                                         filetypes=(('LEAPP Case Data', '*.lcasedata'),))
        if destination_path and os.path.exists(destination_path):
            case_data_load_error = None
            with open(destination_path, 'rt', encoding='utf-8') as case_data_in:
                try:
                    case_data = json.load(case_data_in)
                except:
                    case_data_load_error = 'File was not a valid case data file: invalid format'
            if not case_data_load_error:
                if isinstance(case_data, dict):
                    if case_data.get('leapp') != 'case_data':
                        case_data_load_error = 'File was not a valid case data file'
                    else:
                        c_data = case_data.get('case_data_values', {})
                        case_number_entry.delete(0, 'end')
                        case_number_entry.insert(0, c_data.get('Case Number', ''))
                        case_agency_name_entry.delete(0, 'end')
                        case_agency_name_entry.insert(0, c_data.get('Agency', ''))
                        case_agency_logo_path_entry.delete(0, 'end')
                        case_agency_logo_path_entry.insert(0, c_data.get('Agency Logo Path', ''))
                        case_agency_logo_mimetype.delete(0, 'end')
                        case_agency_logo_mimetype.insert(0, c_data.get('Agency Logo mimetype', ''))
                        case_agency_logo_b64.delete(0, 'end')
                        case_agency_logo_b64.insert(0, c_data.get('Agency Logo base64', ''))
                        case_examiner_entry.delete(0, 'end')
                        case_examiner_entry.insert(0, c_data.get('Examiner', ''))
                else:
                    case_data_load_error = 'File was not a valid case data file: invalid format'
            if case_data_load_error:
                tk_msgbox.showerror(title='Error', message=case_data_load_error, parent=case_window)
            else:
                tk_msgbox.showinfo(
                    title='Load Case Data', message=f'Loaded Case Data: {destination_path}', parent=case_window)

    def add_agency_logo():
        logo_path = tk_filedialog.askopenfilename(parent=case_window,
                                                  title='Add agency logo',
                                                  filetypes=(('All supported files', '*.png *.jpg *.gif'), ))
        if logo_path and os.path.exists(logo_path):
            agency_logo_load_error = None
            with open(logo_path, 'rb') as agency_logo_file:
                agency_logo_mimetype = guess_mime(agency_logo_file)
                if agency_logo_mimetype and 'image' in agency_logo_mimetype:
                    try:
                        agency_logo_base64_encoded = base64.b64encode(agency_logo_file.read())
                    except:
                        agency_logo_load_error = 'Unable to encode the selected file in base64.'
                else:
                    agency_logo_load_error = 'Selected file is not a valid picture file.'
            if agency_logo_load_error:
                tk_msgbox.showerror(title='Error', message=agency_logo_load_error, parent=case_window)
            else:
                case_agency_logo_path_entry.delete(0, 'end')
                case_agency_logo_path_entry.insert(0, logo_path)
                case_agency_logo_mimetype.delete(0, 'end')
                case_agency_logo_mimetype.insert(0, agency_logo_mimetype)
                case_agency_logo_b64.delete(0, 'end')
                case_agency_logo_b64.insert(0, agency_logo_base64_encoded)
                tk_msgbox.showinfo(
                    title='Add agency logo', message=f'{logo_path} was added as Agency logo', parent=case_window)

    case_window = ctk.CTkToplevel(main_window)
    case_window.transient(main_window)
    case_window.configure(fg_color=APP_BG_COLOR)
    case_window_width = 640
    if is_platform_linux():
        case_window_height = 425
    elif is_platform_macos():
        case_window_height = 417
    else:
        case_window_height = 405

    main_window.update_idletasks()
    main_x = main_window.winfo_x()
    main_y = main_window.winfo_y()
    main_w = main_window.winfo_width()
    main_h = main_window.winfo_height()

    margin_width = main_x + (main_w - case_window_width) // 2
    margin_height = main_y + (main_h - case_window_height) // 2

    def geometry_offset(value):
        return f'+{value}' if value >= 0 else str(value)

    case_window.geometry(f'{case_window_width}x{case_window_height}{geometry_offset(margin_width)}{geometry_offset(margin_height)}')
    case_window.resizable(False, False)
    case_window.title('Add Case Data')
    case_window.grid_columnconfigure(0, weight=1)

    def close_case_window():
        case_window.destroy()

    case_window.protocol("WM_DELETE_WINDOW", close_case_window)

    case_title_label = ctk.CTkLabel(case_window, text='Add Case Data', font=('Helvetica', 18, 'bold'), text_color=TEXT_COLOR)
    case_title_label.grid(row=0, column=0, padx=14, pady=7, sticky='w')

    case_number_frame_outer, case_number_frame = create_labelframe(case_window, ' Case Number ')
    case_number_frame_outer.grid(row=1, column=0, padx=14, pady=5, sticky='we')
    case_number_entry = ctk.CTkEntry(
        case_number_frame, textvariable=casedata['Case Number'], 
        corner_radius=RADIUS, fg_color=FRAME_BG_COLOR, text_color=TEXT_COLOR)
    case_number_entry.pack(padx=5, pady=4, fill='x')
    case_number_entry.focus()

    case_agency_frame_outer, case_agency_frame = create_labelframe(case_window, ' Agency ')
    case_agency_frame_outer.grid(row=2, column=0, padx=14, pady=5, sticky='we')
    case_agency_frame.grid_columnconfigure(1, weight=1)
    
    case_agency_name_label = ctk.CTkLabel(case_agency_frame, text="Name:", text_color=TEXT_COLOR)
    case_agency_name_label.grid(row=0, column=0, padx=5, pady=4, sticky='w')
    case_agency_name_entry = ctk.CTkEntry(
        case_agency_frame, textvariable=casedata['Agency'], 
        corner_radius=RADIUS, fg_color=FRAME_BG_COLOR, text_color=TEXT_COLOR)
    case_agency_name_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=4, sticky='we')
    
    case_agency_logo_label = ctk.CTkLabel(case_agency_frame, text="Logo:", text_color=TEXT_COLOR)
    case_agency_logo_label.grid(row=1, column=0, padx=5, pady=6, sticky='w')
    
    case_agency_logo_path_entry = ctk.CTkEntry(
        case_agency_frame, textvariable=casedata['Agency Logo Path'], 
        corner_radius=RADIUS, fg_color=FRAME_BG_COLOR, text_color=TEXT_COLOR)
    case_agency_logo_mimetype = ctk.CTkEntry(
        case_agency_frame, textvariable=casedata['Agency Logo mimetype'], 
        corner_radius=RADIUS, fg_color=FRAME_BG_COLOR, text_color=TEXT_COLOR)
    case_agency_logo_b64 = ctk.CTkEntry(
        case_agency_frame, textvariable=casedata['Agency Logo base64'], 
        corner_radius=RADIUS, fg_color=FRAME_BG_COLOR, text_color=TEXT_COLOR)
    
    case_agency_logo_path_entry.grid(row=1, column=1, padx=5, pady=6, sticky='we')
    case_agency_logo_button = ctk.CTkButton(
        case_agency_frame, text='Add File', command=add_agency_logo,
        corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
        fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
    case_agency_logo_button.grid(row=1, column=2, padx=5, pady=6)

    case_examiner_frame_outer, case_examiner_frame = create_labelframe(case_window, ' Examiner ')
    case_examiner_frame_outer.grid(row=3, column=0, padx=14, pady=5, sticky='we')
    case_examiner_entry = ctk.CTkEntry(
        case_examiner_frame, textvariable=casedata['Examiner'], 
        corner_radius=RADIUS, fg_color=FRAME_BG_COLOR, text_color=TEXT_COLOR)
    case_examiner_entry.pack(padx=5, pady=4, fill='x')

    modules_btn_frame = ctk.CTkFrame(case_window, fg_color="transparent", corner_radius=RADIUS)
    modules_btn_frame.grid(row=4, column=0, padx=14, pady=16, sticky='we')
    modules_btn_frame.grid_columnconfigure(2, weight=1)
    
    load_case_button = ctk.CTkButton(
        modules_btn_frame, text='Load Case Data File', command=load_case,
        corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
        fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
    load_case_button.grid(row=0, column=0, padx=5)
    save_case_button = ctk.CTkButton(
        modules_btn_frame, text='Save Case Data File', command=save_case,
        corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
        fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
    save_case_button.grid(row=0, column=1, padx=5)
    
    clear_case_button = ctk.CTkButton(
        modules_btn_frame, text='Clear', command=clear,
        corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
        fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
    clear_case_button.grid(row=0, column=3, padx=5)
    close_case_button = ctk.CTkButton(
        modules_btn_frame, text='Close', command=close_case_window,
        corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
        fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
    close_case_button.grid(row=0, column=4, padx=5)


check_runtime_dependencies()

main_window = ctk.CTk()
main_window.configure(fg_color=APP_BG_COLOR)
icon = resource_path('icon.png')
loader: typing.Optional[plugin_loader.PluginLoader] = plugin_loader.PluginLoader()
mlist = {}
profile_filename = None

casedata = {
    'Case Number': ctk.StringVar(),
    'Agency': ctk.StringVar(),
    'Agency Logo Path': ctk.StringVar(),
    'Agency Logo mimetype': ctk.StringVar(),
    'Agency Logo base64': ctk.StringVar(),
    'Examiner': ctk.StringVar(),
}
timezone_set = ctk.StringVar()
modules_filter_var = ctk.StringVar()
modules_filter_var.trace_add("write", filter_modules)
pickModules()

main_window.minsize(890, 750)
main_window.title(f'iLEAPP version {leapp_version}')

# Ensure tkinter uses black for dialogs
main_window.option_add('*TkChooseDir*foreground', 'black')
main_window.option_add('*TkFDialog*foreground', 'black')

# Top part of the window
title_frame = ctk.CTkFrame(main_window, fg_color="transparent", corner_radius=RADIUS)
title_frame.pack(padx=14, pady=8, fill='x')

ileapp_img = Image.open(resource_path("iLEAPP_logo.png"))
ileapp_logo = ctk.CTkImage(light_image=ileapp_img, size=ileapp_img.size)
ileapp_logo_label = ctk.CTkLabel(title_frame, image=ileapp_logo, text="")
ileapp_logo_label.pack(side='left')

settings_img = Image.open(resource_path("settings.png")).resize((32, 32))
settings_icon = ctk.CTkImage(light_image=settings_img, size=(32, 32))
settings_label = ctk.CTkLabel(title_frame, image=settings_icon, text="", cursor="hand2")
settings_label.pack(side='right', padx=(10, 0))
settings_label.bind("<Button-1>", lambda e: open_settings_window())

leapps_img = Image.open(resource_path("leapps_i_logo.png")).resize((110, 51))
leapps_logo = ctk.CTkImage(light_image=leapps_img, size=(110, 51))
leapps_logo_label = ctk.CTkLabel(title_frame, image=leapps_logo, text="", cursor="target")
leapps_logo_label.pack(side='right')
leapps_logo_label.bind("<Button-1>", lambda e: open_website("https://leapps.org"))

if '--selfcheck' in sys.argv[1:]:
    print(f'selfcheck passed: {len(loader)} artifacts, Tk {main_window.tk.call("info", "patchlevel")}')
    main_window.destroy()
    sys.exit(0)

input_frame_outer, input_frame = create_labelframe(
    main_window, 
    ' Select the file (tar, zip, gz, raw image, E01, AFF, DMG or virtual disk, L01 or AD1) or directory of the target iOS full file system extraction or a backup for parsing: ')
input_frame_outer.pack(padx=14, pady=2, fill='x')

input_entry = ctk.CTkEntry(
    input_frame, corner_radius=RADIUS, 
    fg_color=FRAME_BG_COLOR, text_color=TEXT_COLOR)
input_entry.pack(side='left', padx=5, pady=4, fill='x', expand=True)

input_history_button = ctk.CTkButton(
    input_frame, text='▼', width=30,
    command=lambda: show_history_menu(input_history_button, 'input'),
    corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
    fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
input_history_button.pack(side='left', padx=2, pady=4)

input_file_button = ctk.CTkButton(
    input_frame, text='Browse File', command=lambda: select_input('file'),
    corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
    fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
input_file_button.pack(side='left', padx=5, pady=4)

input_folder_button = ctk.CTkButton(
    input_frame, text='Browse Folder', command=lambda: select_input('folder'),
    corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
    fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
input_folder_button.pack(side='left', padx=5, pady=4)


keychain_frame_outer, keychain_frame = create_labelframe(
    main_window,
    ' Optional: keychain file captured from the device, used to decrypt apps such as Signal. Leave blank to use one the extraction carries: ')
keychain_frame_outer.pack(padx=14, pady=2, fill='x')

keychain_entry = ctk.CTkEntry(
    keychain_frame, corner_radius=RADIUS, 
    fg_color=FRAME_BG_COLOR, text_color=TEXT_COLOR)
keychain_entry.pack(side='left', padx=5, pady=4, fill='x', expand=True)

keychain_clear_button = ctk.CTkButton(
    keychain_frame, text='Clear', width=60, command=clear_keychain,
    corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
    fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
keychain_clear_button.pack(side='left', padx=2, pady=4)

keychain_file_button = ctk.CTkButton(
    keychain_frame, text='Browse File', command=select_keychain,
    corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
    fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
keychain_file_button.pack(side='left', padx=5, pady=4)


output_frame_outer, output_frame = create_labelframe(main_window, ' Select Output Path ')
output_frame_outer.pack(padx=14, pady=5, fill='x')

output_path_row = ctk.CTkFrame(output_frame, fg_color="transparent", corner_radius=RADIUS)
output_path_row.pack(fill='x')
output_entry = ctk.CTkEntry(
    output_path_row, corner_radius=RADIUS, 
    fg_color=FRAME_BG_COLOR, text_color=TEXT_COLOR)
output_entry.pack(side='left', padx=5, pady=4, fill='x', expand=True)

output_history_button = ctk.CTkButton(
    output_path_row, text='▼', width=30,
    command=lambda: show_history_menu(output_history_button, 'output'),
    corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
    fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
output_history_button.pack(side='left', padx=2, pady=4)

output_folder_button = ctk.CTkButton(
    output_path_row, text='Browse Folder', command=select_output,
    corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
    fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
output_folder_button.pack(side='left', padx=5, pady=4)

output_folder_name_row = ctk.CTkFrame(output_frame, fg_color="transparent", corner_radius=RADIUS)
output_folder_name_row.pack(fill='x', padx=5, pady=(0, 4))
ctk.CTkLabel(output_folder_name_row, text='Folder name:', text_color=TEXT_COLOR).pack(side='left', padx=(0, 5))

output_folder_name_entry = ctk.CTkEntry(
    output_folder_name_row, corner_radius=RADIUS, 
    fg_color=FRAME_BG_COLOR, text_color=TEXT_COLOR)
output_folder_name_entry.insert(0, default_output_folder_name())

def validate_entry(P):
    return allow_output_folder_name_chars(P)
vcmd = (main_window.register(validate_entry), '%P')
output_folder_name_entry.configure(validate='key', validatecommand=vcmd)
output_folder_name_entry.pack(side='left', fill='x', expand=True)

mlist_frame_outer, mlist_frame = create_labelframe(main_window, ' Available Modules: ')
mlist_frame_outer.pack(padx=14, pady=5, expand=True, fill='both')

button_frame = ctk.CTkFrame(mlist_frame, fg_color="transparent", corner_radius=RADIUS)
button_frame.pack(pady=4, fill='x')

if is_platform_macos():
    modules_filter_icon = ctk.CTkLabel(button_frame, text="\U0001F50E", text_color=TEXT_COLOR)
else:
    magnif_img = Image.open(resource_path("magnif_glass.png"))
    modules_filter_img = ctk.CTkImage(light_image=magnif_img, size=(16, 16))
    modules_filter_icon = ctk.CTkLabel(button_frame, image=modules_filter_img, text="")
modules_filter_icon.pack(padx=4, side='left')

modules_filter_entry = ctk.CTkEntry(
    button_frame, textvariable=modules_filter_var, 
    corner_radius=RADIUS, fg_color=FRAME_BG_COLOR, text_color=TEXT_COLOR)
modules_filter_entry.pack(padx=2, fill='x', expand=True, side='left')

all_button = ctk.CTkButton(
    button_frame, text='Select All', command=select_all,
    corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
    fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
all_button.pack(padx=5, side='left')

none_button = ctk.CTkButton(
    button_frame, text='Deselect All', command=deselect_all,
    corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
    fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
none_button.pack(padx=5, side='left')

load_button = ctk.CTkButton(
    button_frame, text='Load Profile', command=load_profile,
    corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
    fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
load_button.pack(padx=5, side='left')

save_button = ctk.CTkButton(
    button_frame, text='Save Profile', command=save_profile,
    corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
    fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
save_button.pack(padx=5, side='left')

module_list_frame = ctk.CTkFrame(mlist_frame, fg_color="transparent", corner_radius=RADIUS)
module_list_frame.pack(expand=True, fill='both')

mlist_text = ctk.CTkScrollableFrame(module_list_frame, corner_radius=RADIUS, fg_color=FRAME_BG_COLOR)
mlist_text.pack(expand=True, fill='both', padx=4)

def build_checkboxes():
    """Build all checkboxes once and store them in the mlist list."""
    for artifact_name, module_infos in mlist.items():
        cb = ctk.CTkCheckBox(
            mlist_text,
            text=f'{module_infos[0]} [{module_infos[1]} | {module_infos[2]}.py]',
            variable=module_infos[3],
            onvalue=True,
            offvalue=False,
            command=get_selected_modules,
            corner_radius=RADIUS,
            border_width=BORDER_WIDTH,
            border_color=BORDER_COLOR,
            fg_color=WIDGET_COLOR,
            hover_color=WIDGET_HOVER,
            text_color=TEXT_COLOR,
            checkmark_color=CHECKMARK_COLOR
        )
        module_infos.append(cb)  # Index 4
        cb.pack(anchor='w', pady=2, padx=5)

# Generate list exactly once
build_checkboxes()

main_window.bind("<Control-f>", lambda event: modules_filter_entry.focus_set())
main_window.bind("<Control-i>", lambda event: input_entry.focus_set())
main_window.bind("<Control-o>", lambda event: output_entry.focus_set())

bottom_frame = ctk.CTkFrame(main_window, fg_color="transparent", corner_radius=RADIUS)
bottom_frame.pack(side='bottom', padx=16, pady=6, fill='x', before=mlist_frame_outer)

process_button = ctk.CTkButton(
    bottom_frame, text='Process', command=lambda: process(casedata),
    corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
    fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
process_button.pack(side='left', padx=5)

close_button = ctk.CTkButton(
    bottom_frame, text='Close', command=main_window.quit,
    corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
    fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
close_button.pack(side='left', padx=5)

case_data_button_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent", corner_radius=RADIUS)
case_data_button_frame.pack(side='left', expand=True, fill='x')

case_data_button = ctk.CTkButton(
    case_data_button_frame, text='Case Data', command=case_data,
    corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=BORDER_COLOR,
    fg_color=WIDGET_COLOR, hover_color=WIDGET_HOVER, text_color=TEXT_COLOR)
case_data_button.pack(padx=5)

selected_modules_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent", corner_radius=RADIUS)
selected_modules_frame.pack(side='right', padx=5)

selected_modules_label = ctk.CTkLabel(selected_modules_frame, text='Number of selected modules: ', text_color=TEXT_COLOR)
selected_modules_label.pack(anchor='e')

auto_unselected_modules_label = ctk.CTkLabel(
    selected_modules_frame,
    text='(Modules making some time to run were automatically unselected)',
    font=('Helvetica', 10), text_color=TEXT_COLOR)
auto_unselected_modules_label.pack(anchor='e')
get_selected_modules()

logtext_frame = ctk.CTkFrame(main_window, corner_radius=RADIUS, fg_color="transparent")
log_text = ctk.CTkTextbox(logtext_frame, corner_radius=RADIUS, fg_color=FRAME_BG_COLOR, text_color=TEXT_COLOR)
log_text.pack(expand=True, fill='both')

progress_bar_frame = ctk.CTkFrame(main_window, corner_radius=RADIUS, fg_color="transparent")
progress_bar = ctk.CTkProgressBar(progress_bar_frame, orientation='horizontal', corner_radius=RADIUS, fg_color=FRAME_BG_COLOR)
progress_bar.set(0)
progress_bar.pack(padx=16, pady=20, fill='x')

def geometry_offset(value):
    return f'+{value}' if value >= 0 else str(value)

def center_main_window_macos(window, width, height):
    window.update_idletasks()
    mx, my = window.winfo_pointerxy()
    window.geometry("+0+0")
    window.update_idletasks()
    pw = window.winfo_screenwidth()
    ph = window.winfo_screenheight()

    window.geometry(f'{geometry_offset(mx)}{geometry_offset(my)}')
    window.update_idletasks()
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    vx = window.winfo_vrootx()

    if mx < 0:
        mon_x, mon_y, mon_w, mon_h = vx, 0, abs(vx), sh
    elif mx >= pw:
        mon_x, mon_y, mon_w, mon_h = pw, 0, sw, sh
    else:
        mon_x, mon_y, mon_w, mon_h = 0, 0, pw, ph

    start_x = mon_x + (mon_w - width) // 2
    start_y = mon_y + (mon_h - height) // 2
    window.geometry(f'{width}x{height}{geometry_offset(start_x)}{geometry_offset(start_y)}')

# Bring window to front once on startup without binding it to a recurring event
main_window.attributes('-topmost', True)
main_window.update()
main_window.attributes('-topmost', False)
main_window.focus_force()

main_window.protocol('WM_DELETE_WINDOW', close_main_window)

if is_platform_macos():
    center_main_window_macos(main_window, 890, 690)
main_window.mainloop()