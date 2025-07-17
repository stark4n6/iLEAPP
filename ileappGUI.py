import tkinter as tk
import customtkinter as ctk
import typing
import json
import ileapp
import webbrowser
import base64
import os
import sys
from pathlib import Path

import scripts.plugin_loader as plugin_loader

from PIL import Image, ImageTk
from tkinter import filedialog as tk_filedialog, messagebox as tk_msgbox
from scripts.version_info import ileapp_version
from scripts.search_files import *
from scripts.tz_offset import tzvalues
from scripts.modules_to_exclude import modules_to_exclude
from scripts.lavafuncs import * # Assuming this contains necessary functions like is_platform_windows, initialize_lava, lava_finalize_output, OutputParameters, guess_mime

# Set CustomTkinter appearance mode and color theme
ctk.set_appearance_mode("Dark")  # Options: "Light", "Dark", "System"
ctk.set_default_color_theme("blue")  # Options: "blue", "green", "dark-blue"

# Custom class to redirect stdout to the CTkTextbox
class TextRedirector(object):
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, str_to_write):
        self.widget.configure(state='normal') # Enable writing
        self.widget.insert(ctk.END, str_to_write, (self.tag,))
        self.widget.see(ctk.END) # Scroll to the end
        self.widget.configure(state='disabled') # Disable writing
        self.widget.update_idletasks() # Force update the GUI

    def flush(self):
        # This method is required for file-like objects, but can be a no-op for a TextRedirector
        pass

def pickModules():
    '''Create a list of available modules:
        - iTunesBackupInfo, iTunesBackupInstalledApplications, lastBuild and Ph100-UFED-device-values-Plist that need 
        to be executed first are excluded
        - logarchive_artifacts is also excluded as it uses the LAVA SQLite database to extract 
        relevant event messages from the logarchive table and must be executed only if logarchive 
        module has been already executed
        - ones that take a long time to run are deselected by default'''
    global mlist
    for plugin in sorted(loader.plugins, key=lambda p: p.category.upper()):
        if (plugin.module_name == 'iTunesBackupInfo'
                or plugin.name == 'lastBuild'
                or plugin.module_name == 'logarchive' and plugin.name != 'logarchive'):
            continue
        # Items that take a long time to execute are deselected by default
        # and referenced in the modules_to_exclude list in an external file (modules_to_exclude.py).
        plugin_enabled = ctk.BooleanVar(value=False) if plugin.module_name in modules_to_exclude else ctk.BooleanVar(value=True)
        plugin_module_name = plugin.artifact_info.get('name', plugin.name) if hasattr(plugin, 'artifact_info') else plugin.name
        mlist[plugin.name] = [plugin.category, plugin_module_name, plugin.module_name, plugin_enabled]


def get_selected_modules():
    '''Update the number and return the list of selected modules'''
    selected_modules = []

    for artifact_name, module_infos in mlist.items():
        if module_infos[-1].get():
            selected_modules.append(artifact_name)

    selected_modules_label.configure(text=f'Number of selected modules: {len(selected_modules)} / {len(mlist)}')
    return selected_modules


def select_all():
    '''Select all modules in the list of available modules and execute get_selected_modules'''
    for module_infos in mlist.values():
        module_infos[-1].set(True)

    get_selected_modules()


def deselect_all():
    '''Unselect all modules in the list of available modules and execute get_selected_modules'''
    for module_infos in mlist.values():
        module_infos[-1].set(False)

    get_selected_modules()


def filter_modules(*args):
    # Clear existing checkboxes in the scrollable frame
    for widget in mlist_scrollable_frame.winfo_children():
        widget.destroy()

    filter_term = modules_filter_var.get().lower()

    for artifact_name, module_infos in mlist.items():
        filter_modules_info = f"{module_infos[0]} {module_infos[1]}".lower()
        if filter_term in filter_modules_info:
            cb = ctk.CTkCheckBox(mlist_scrollable_frame, # Place checkbox in the scrollable frame
                                 text=f'{module_infos[0]} [{module_infos[1]} | {module_infos[2]}.py]',
                                 variable=module_infos[-1], onvalue=True, offvalue=False,
                                 command=get_selected_modules)
            cb.pack(padx=5, pady=2, anchor='w') # Use pack for simple vertical arrangement


def load_profile():
    '''Select modules from a profile file'''
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
                            module_infos[-1].set(True)
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
    '''Save selected modules in a profile file'''
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


# The scroll function is no longer needed as CTkScrollableFrame handles its own scrolling
# def scroll(event):
#     '''Continue to scroll the list with mouse wheel when cursor hover a checkbutton'''
#     parent = event.widget.winfo_toplevel() # Get the toplevel window
#     if mlist_text.winfo_exists(): # Check if mlist_text still exists
#         mlist_text.yview_scroll(-1 * (event.delta // 120), "units")


def ValidateInput():
    '''Returns tuple (success, extraction_type)'''
    i_path = input_entry.get()  # input file/folder
    o_path = output_entry.get()  # output folder
    ext_type = ''

    # check input
    if len(i_path) == 0:
        tk_msgbox.showerror(title='Error', message='No INPUT file or folder selected!', parent=main_window)
        return False, ext_type
    elif not os.path.exists(i_path):
        tk_msgbox.showerror(title='Error', message='INPUT file/folder does not exist!', parent=main_window)
        return False, ext_type
    elif os.path.isdir(i_path) and (os.path.exists(os.path.join(i_path, 'Manifest.db')) or os.path.exists(os.path.join(i_path, 'Manifest.mbdb'))):
        ext_type = 'itunes'
    elif os.path.isdir(i_path):
        ext_type = 'fs'
    else:
        ext_type = Path(i_path).suffix[1:].lower()

    # check output now
    if len(o_path) == 0:  # output folder
        tk_msgbox.showerror(title='Error', message='No OUTPUT folder selected!', parent=main_window)
        return False, ext_type

    # check if at least one module is selected
    if len(get_selected_modules()) == 0:
        tk_msgbox.showerror(title='Error', message='No module selected for processing!', parent=main_window)
        return False, ext_type

    return True, ext_type


def open_report(report_path):
    '''Open report and Quit after processing completed'''
    webbrowser.open_new_tab('file://' + report_path)
    main_window.quit()


def open_website(url):
    webbrowser.open_new_tab(url)


def resource_path(filename):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, 'assets', filename)

def process(casedata):
    '''Execute selected modules and create reports'''
    # Clear the log text box at the start of processing
    log_text.configure(state='normal')
    log_text.delete('1.0', ctk.END)
    log_text.configure(state='disabled')
    main_window.update_idletasks() # Ensure it's cleared visually

    is_valid, extracttype = ValidateInput()

    if is_valid:
        GuiWindow.window_handle = main_window
        input_path = input_entry.get()
        output_folder = output_entry.get()

        # ios file system extractions contain paths > 260 char, which causes problems
        # This fixes the problem by prefixing \\?\ on each windows path.
        if is_platform_windows():
            if input_path[1] == ':' and extracttype == 'fs': input_path = '\\\\?\\' + input_path.replace('/', '\\')
            if output_folder[1] == ':': output_folder = '\\\\?\\' + output_folder.replace('/', '\\')

        # re-create modules list based on user selection
        selected_modules = get_selected_modules()
        
        # Check if there are selected modules to avoid division by zero
        if not selected_modules:
            tk_msgbox.showerror(title='Error', message='No modules selected for processing!', parent=main_window)
            return

        selected_modules_objects = [loader[module] for module in selected_modules]
        
        # Removed progress_bar.configure(maximum=len(selected_modules))
        # CTkProgressBar works with values from 0 to 1.
        # We will set the progress in the loop.

        casedata = {key: value.get() for key, value in casedata.items()}
        out_params = OutputParameters(output_folder)
        wrap_text = True
        time_offset = timezone_set.get()
        if time_offset == '':
            time_offset = 'UTC'

        logtext_frame.grid(row=1, column=0, rowspan=3, padx=14, pady=4, sticky='nswe')
        bottom_frame.grid_remove()
        progress_bar.grid(padx=16, sticky='we')

        initialize_lava(input_path, out_params.report_folder_base, extracttype)

        # Set initial progress to 0
        progress_bar.set(0)
        main_window.update_idletasks()

        # Temporarily redirect stdout to the log_text widget
        old_stdout = sys.stdout
        sys.stdout = TextRedirector(log_text, "stdout")

        try:
            crunch_successful = ileapp.crunch_artifacts(
                selected_modules_objects, extracttype, input_path, out_params, wrap_text, loader,
                casedata, time_offset, profile_filename) 
            
            lava_finalize_output(out_params.report_folder_base)

        finally:
            # Restore original stdout
            sys.stdout = old_stdout

        # Set final progress to 1 (100%)
        progress_bar.set(1)
        main_window.update_idletasks()

        if crunch_successful:
            report_path = os.path.join(out_params.report_folder_base, 'index.html')
            if report_path.startswith('\\\\?\\'):  # windows
                report_path = report_path[4:]
            if report_path.startswith('\\\\'):  # UNC path
                report_path = report_path[2:]
            progress_bar.grid_remove()
            if lava_only_artifacts: # Assuming lava_only_artifacts is defined elsewhere
                message = "You have selected artifacts that are likely to return too much data "
                message += "to be viewed in a Web browser.\n\n"
                message += "Please see the 'LAVA only artifacts' tab in the HTML report for a list of these artifacts "
                message += "and instructions on how to view them."
                tk_msgbox.showwarning(
                    title="Important information",
                    message=message,
                    parent=main_window)
            open_report_button = ctk.CTkButton(main_window, text='Open Report & Close', command=lambda: open_report(report_path))
            open_report_button.grid(ipadx=8)
        else:
            log_path = out_params.screen_output_file_path
            if log_path.startswith('\\\\?\\'):  # windows
                log_path = log_path[4:]
            tk_msgbox.showerror(
                title='Error',
                message=f'Processing failed  :( \nSee log for error details..\nLog file located at {log_path}',
                parent=main_window)


def select_input(button_type):
    '''Select source and insert its path into input field'''
    if button_type == 'file':
        input_filename = tk_filedialog.askopenfilename(parent=main_window,
                                                       title='Select a file',
                                                       filetypes=(('All supported files', '*.tar *.zip *.gz'),
                                                                  ('tar file', '*.tar'), ('zip file', '*.zip'),
                                                                  ('gz file', '*.gz')))
    else:
        input_filename = tk_filedialog.askdirectory(parent=main_window, title='Select a folder')
    input_entry.delete(0, 'end')
    input_entry.insert(0, input_filename)


def select_output():
    '''Select target and insert its path into output field'''
    output_filename = tk_filedialog.askdirectory(parent=main_window, title='Select a folder')
    output_entry.delete(0, 'end')
    output_entry.insert(0, output_filename)


def case_data():
    # GUI layout
    ## Case Data
    '''Add Case Data window'''
    global casedata

    def clear():
        '''Remove the contents of all fields'''
        case_number_entry.delete(0, 'end')
        case_agency_name_entry.delete(0, 'end')
        case_agency_logo_path_entry.delete(0, 'end')
        case_agency_logo_mimetype.delete(0, 'end')
        case_agency_logo_b64.delete(0, 'end')
        case_examiner_entry.delete(0, 'end')

    def save_case():
        '''Save case data in a Case Data file'''
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
        '''Import case data from a Case Data file'''
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
                        for key, val in case_data.get('case_data_values', {}).items():
                            if key in casedata:
                                casedata[key].set(val)
                        tk_msgbox.showinfo(
                            title='Load Case Data', message=f'Loaded Case Data: {destination_path}', parent=case_window)
                else:
                    case_data_load_error = 'File was not a valid case data file: invalid format'
            if case_data_load_error:
                tk_msgbox.showerror(title='Error', message=case_data_load_error, parent=case_window)
            else:
                tk_msgbox.showinfo(
                    title='Load Case Data', message=f'Loaded Case Data: {destination_path}', parent=case_window)

    def add_agency_logo():
        '''Import image file and convert it into base64'''
        logo_path = tk_filedialog.askopenfilename(parent=case_window,
                                                           title='Add agency logo',
                                                           filetypes=(('All supported files', '*.png *.jpg *.gif'), ))

        if logo_path and os.path.exists(logo_path):
            agency_logo_load_error = None
            with open(logo_path, 'rb') as agency_logo_file:
                agency_logo_file.seek(0) # Reset file pointer for guess_mime
                agency_logo_mimetype_val = guess_mime(agency_logo_file) # Assuming guess_mime is available
                if agency_logo_mimetype_val and 'image' in agency_logo_mimetype_val:
                    try:
                        agency_logo_file.seek(0) # Reset file pointer again for base64.b64encode
                        agency_logo_base64_encoded = base64.b64encode(agency_logo_file.read())
                    except Exception as e:
                        agency_logo_load_error = f'Unable to encode the selected file in base64: {e}'
                else:
                    agency_logo_load_error = 'Selected file is not a valid picture file.'
            if agency_logo_load_error:
                tk_msgbox.showerror(title='Error', message=agency_logo_load_error, parent=case_window)
            else:
                casedata['Agency Logo Path'].set(logo_path)
                casedata['Agency Logo mimetype'].set(agency_logo_mimetype_val)
                casedata['Agency Logo base64'].set(agency_logo_base64_encoded)
                tk_msgbox.showinfo(
                    title='Add agency logo', message=f'{logo_path} was added as Agency logo', parent=case_window)

    ### Case Data Window creation
    case_window = ctk.CTkToplevel(main_window)
    case_window_width = 650
    case_window_height = 325 if is_platform_linux() else 305

    #### Places Case Data window in the center of the screen
    screen_width = main_window.winfo_screenwidth()
    screen_height = main_window.winfo_screenheight()
    margin_width = (screen_width - case_window_width) // 2
    margin_height = (screen_height - case_window_height) // 2

    #### Case Data window properties
    case_window.geometry(f'{case_window_width}x{case_window_height}+{margin_width}+{margin_height}')
    case_window.resizable(False, False)
    case_window.title('Add Case Data')
    case_window.grid_columnconfigure(0, weight=1)

    #### Layout
    case_title_label = ctk.CTkLabel(case_window, text='Add Case Data', font=ctk.CTkFont(family='Helvetica', size=18, weight='bold'))
    case_title_label.grid(row=0, column=0, padx=14, pady=7, sticky='w')

    case_number_frame = ctk.CTkFrame(case_window)
    case_number_frame.grid(row=1, column=0, padx=14, pady=5, sticky='we')
    # Changed from pack to grid for consistency within case_number_frame
    ctk.CTkLabel(case_number_frame, text="Case Number:").grid(row=0, column=0, padx=5, pady=4, sticky="w")
    case_number_entry = ctk.CTkEntry(case_number_frame, textvariable=casedata['Case Number'])
    case_number_entry.grid(row=0, column=1, padx=5, pady=4, sticky='we', columnspan=2) # Added columnspan for entry
    case_number_entry.focus()
    case_number_frame.grid_columnconfigure(1, weight=1) # Make entry expand

    case_agency_frame = ctk.CTkFrame(case_window)
    case_agency_frame.grid(row=2, column=0, padx=14, pady=5, sticky='we')
    case_agency_frame.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(case_agency_frame, text="Agency Name:").grid(row=0, column=0, padx=5, pady=4, sticky='w')
    case_agency_name_entry = ctk.CTkEntry(case_agency_frame, textvariable=casedata['Agency'])
    case_agency_name_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=4, sticky='we')
    ctk.CTkLabel(case_agency_frame, text="Agency Logo:").grid(row=1, column=0, padx=5, pady=6, sticky='w')
    case_agency_logo_path_entry = ctk.CTkEntry(case_agency_frame, textvariable=casedata['Agency Logo Path'])
    case_agency_logo_path_entry.grid(row=1, column=1, padx=5, pady=6, sticky='we')
    case_agency_logo_mimetype = ctk.CTkEntry(case_agency_frame, textvariable=casedata['Agency Logo mimetype']) # Hidden
    case_agency_logo_b64 = ctk.CTkEntry(case_agency_frame, textvariable=casedata['Agency Logo base64']) # Hidden
    case_agency_logo_button = ctk.CTkButton(case_agency_frame, text='Add File', command=add_agency_logo)
    case_agency_logo_button.grid(row=1, column=2, padx=5, pady=6)

    case_examiner_frame = ctk.CTkFrame(case_window)
    case_examiner_frame.grid(row=3, column=0, padx=14, pady=5, sticky='we')
    # Changed from pack to grid for consistency within case_examiner_frame
    ctk.CTkLabel(case_examiner_frame, text="Examiner:").grid(row=0, column=0, padx=5, pady=4, sticky="w")
    case_examiner_entry = ctk.CTkEntry(case_examiner_frame, textvariable=casedata['Examiner'])
    # Removed fill='x' as it's not a valid grid option. sticky='we' handles horizontal expansion.
    case_examiner_entry.grid(row=0, column=1, padx=5, pady=4, sticky='we', columnspan=2) 
    case_examiner_frame.grid_columnconfigure(1, weight=1) # Make entry expand

    modules_btn_frame = ctk.CTkFrame(case_window)
    modules_btn_frame.grid(row=4, column=0, padx=14, pady=16, sticky='we')
    modules_btn_frame.grid_columnconfigure(2, weight=1)
    load_case_button = ctk.CTkButton(modules_btn_frame, text='Load Case Data File', command=load_case)
    load_case_button.grid(row=0, column=0, padx=5)
    save_case_button = ctk.CTkButton(modules_btn_frame, text='Save Case Data File', command=save_case)
    save_case_button.grid(row=0, column=1, padx=5)
    # CustomTkinter doesn't have a direct equivalent of ttk.Separator with weight,
    # so we can use an empty column for spacing or adjust padx/grid_columnconfigure.
    # For simplicity, I'll just use a larger padx for the next buttons.
    clear_case_button = ctk.CTkButton(modules_btn_frame, text='Clear', command=clear)
    clear_case_button.grid(row=0, column=3, padx=(20,5)) # Add left padding
    close_case_button = ctk.CTkButton(modules_btn_frame, text='Close', command=case_window.destroy)
    close_case_button.grid(row=0, column=4, padx=5)

    case_window.grab_set()


class GuiWindow:
    window_handle = None # Placeholder for the main window reference

# Main window creation
main_window = ctk.CTk()
window_width = 890
window_height = 800 # Increased window height

# Variables
icon = resource_path('icon.png')
loader: typing.Optional[plugin_loader.PluginLoader] = None
loader = plugin_loader.PluginLoader()
mlist = {}
profile_filename = None
casedata = {'Case Number': ctk.StringVar(),
            'Agency': ctk.StringVar(),
            'Agency Logo Path': ctk.StringVar(),
            'Agency Logo mimetype': ctk.StringVar(),
            'Agency Logo base64': ctk.StringVar(),
            'Examiner': ctk.StringVar(),
            }
timezone_set = ctk.StringVar()
modules_filter_var = ctk.StringVar()
modules_filter_var.trace_add("write", filter_modules)  # Trigger filtering on input change
pickModules()

# Theme properties - CustomTkinter handles most of this through set_appearance_mode and set_default_color_theme
# These are less directly used for widget styling like in ttk
# theme_bgcolor = '#2c2825'
# theme_inputcolor = '#705e52'
# theme_fgcolor = '#fdcb52'

if is_platform_macos():
    mlist_window_height = 24
    log_text_height = 36
elif is_platform_linux():
    mlist_window_height = 17
    log_text_height = 28
else:
    mlist_window_height = 19
    log_text_height = 29

# Places main window in the center
screen_width = main_window.winfo_screenwidth()
screen_height = main_window.winfo_screenheight()
margin_width = (screen_width - window_width) // 2
margin_height = (screen_height - window_height) // 2

# Main window properties
main_window.geometry(f'{window_width}x{window_height}+{margin_width}+{margin_height}')
main_window.title(f'iLEAPP version {ileapp_version}')
main_window.resizable(False, False)
# background color is handled by ctk.set_appearance_mode
# logo_icon = ctk.CTkImage(Image.open(icon), size=(16, 16)) # For CustomTkinter title bar icon, typically set via .wm_iconphoto or .iconbitmap
# main_window.wm_iconphoto(True, tk.PhotoImage(file=icon)) # Still uses PhotoImage for standard Tkinter icon
try:
    photo_icon = tk.PhotoImage(file=icon)
    main_window.wm_iconphoto(True, photo_icon)
except Exception as e:
    print(f"Could not load icon: {e}")

main_window.grid_columnconfigure(0, weight=1)

# Main Window Layout
### Top part of the window
title_frame = ctk.CTkFrame(main_window, fg_color="transparent") # Use transparent for frame if just for layout
title_frame.grid(padx=14, pady=8, sticky='we')
title_frame.grid_columnconfigure(0, weight=1)

# For images, CustomTkinter uses CTkImage. Use light/dark images if you want them to change with theme.
ileapp_logo_image = ctk.CTkImage(Image.open(resource_path("iLEAPP_logo.png")), size=(230, 70)) # Adjust size as needed
ileapp_logo_label = ctk.CTkLabel(title_frame, image=ileapp_logo_image, text="") # text="" to only show image
ileapp_logo_label.grid(row=0, column=0, sticky='w')

leapps_logo_image = ctk.CTkImage(Image.open(resource_path("leapps_i_logo.png")).resize((110, 51)), size=(110, 51))
leapps_logo_label = ctk.CTkLabel(title_frame, image=leapps_logo_image, text="", cursor="hand2") # hand2 for pointer
leapps_logo_label.grid(row=0, column=1, sticky='e') # Changed sticky to 'e' to align right
leapps_logo_label.bind("<Button-1>", lambda e: open_website("https://leapps.org"))

### Input output selection
input_frame = ctk.CTkFrame(
    main_window) # CTkFrame does not have a 'text' option for labelFrame, use CTkLabel
# Changed from pack to grid for consistency within input_frame
ctk.CTkLabel(input_frame, text='Select the file (tar/zip/gz) or directory of the target iOS full file system extraction for parsing: ').grid(row=0, column=0, columnspan=3, padx=10, pady=(5,0), sticky="w")
input_frame.grid(padx=14, pady=2, sticky='we')
input_frame.grid_columnconfigure(0, weight=1)
input_entry = ctk.CTkEntry(input_frame)
input_entry.grid(row=1, column=0, padx=5, pady=4, sticky='we')
input_file_button = ctk.CTkButton(input_frame, text='Browse File', command=lambda: select_input('file'))
input_file_button.grid(row=1, column=1, padx=5, pady=4)
input_folder_button = ctk.CTkButton(input_frame, text='Browse Folder', command=lambda: select_input('folder'))
input_folder_button.grid(row=1, column=2, padx=5, pady=4)

output_frame = ctk.CTkFrame(main_window)
# Changed from pack to grid for consistency within output_frame
ctk.CTkLabel(output_frame, text='Select Output Folder: ').grid(row=0, column=0, columnspan=2, padx=10, pady=(5,0), sticky="w")
output_frame.grid(padx=14, pady=5, sticky='we')
output_frame.grid_columnconfigure(0, weight=1)
output_entry = ctk.CTkEntry(output_frame)
output_entry.grid(row=1, column=0, padx=5, pady=4, sticky='we')
output_folder_button = ctk.CTkButton(output_frame, text='Browse Folder', command=select_output)
output_folder_button.grid(row=1, column=1, padx=5, pady=4)

mlist_frame = ctk.CTkFrame(main_window)
# Changed from pack to grid for consistency within mlist_frame
ctk.CTkLabel(mlist_frame, text='Available Modules: ').grid(row=0, column=0, columnspan=2, padx=10, pady=(5,0), sticky="w")
mlist_frame.grid(padx=14, pady=5, sticky='we')
mlist_frame.grid_columnconfigure(0, weight=1)

button_frame = ctk.CTkFrame(mlist_frame, fg_color="transparent")
button_frame.grid(row=1, column=0, columnspan=2,pady=4, sticky='we')
button_frame.grid_columnconfigure(1, weight=1)

# Using CTkImage for filter icon
if is_platform_macos():
    modules_filter_icon = ctk.CTkLabel(button_frame, text="\U0001F50E")
    modules_filter_icon.grid(row=0, column=0, padx=4)
else:
    modules_filter_img = ctk.CTkImage(Image.open(resource_path("magnif_glass.png")), size=(16, 16))
    modules_filter_icon = ctk.CTkLabel(button_frame, image=modules_filter_img, text="")
    modules_filter_icon.grid(row=0, column=0, padx=4)

modules_filter_entry = ctk.CTkEntry(button_frame, textvariable=modules_filter_var)
modules_filter_entry.grid(row=0, column=1, padx=1, sticky='we')
# CustomTkinter does not have direct separator widgets. You can use frames or adjust padding.
# For simplicity, using padding here.
all_button = ctk.CTkButton(button_frame, text='Select All', command=select_all)
all_button.grid(row=0, column=3, padx=(10,5)) # Add left padding for separator effect
none_button = ctk.CTkButton(button_frame, text='Deselect All', command=deselect_all)
none_button.grid(row=0, column=4, padx=5)
load_button = ctk.CTkButton(button_frame, text='Load Profile', command=load_profile)
load_button.grid(row=0, column=6, padx=(10,5)) # Add left padding
save_button = ctk.CTkButton(button_frame, text='Save Profile', command=save_profile)
save_button.grid(row=0, column=7, padx=5)

# Use CTkScrollableFrame to hold the checkboxes
mlist_scrollable_frame = ctk.CTkScrollableFrame(mlist_frame, height=mlist_window_height * 20) # Approx height based on lines
mlist_scrollable_frame.grid(row=2, column=0, sticky='nswe', padx=5, pady=5) # Adjust row for the label
mlist_frame.grid_rowconfigure(2, weight=1) # Make the scrollable frame expand vertically

# The mlist_text (CTkTextbox) is no longer used for checkboxes,
# so we remove its declaration and related configurations for checkboxes.
# If it was intended for something else, it would need to be re-evaluated.
# For now, assuming it was solely for the checkbox list.

filter_modules() # Call filter_modules to populate the scrollable frame

# Remove bindings related to the old mlist_text scroll and Checkbuttons,
# as CTkScrollableFrame handles its own scrolling.
# main_window.bind_class('CTkCheckBox', '<MouseWheel>', scroll)
# main_window.bind_class('CTkCheckBox', '<Button-4>', scroll)
# main_window.bind_class('CTkCheckBox', '<Button-5>', scroll)

main_window.bind("<Control-f>", lambda event: modules_filter_entry.focus_set()) # Focus on The Filter Field
main_window.bind("<Control-i>", lambda event: input_entry.focus_set()) # Focus on the Input Field
main_window.bind("<Control-o>", lambda event: output_entry.focus_set()) # Focus on the Output Field

### Process
bottom_frame = ctk.CTkFrame(main_window, fg_color="transparent")
bottom_frame.grid(padx=16, pady=6, sticky='we')
bottom_frame.grid_columnconfigure(2, weight=1)
bottom_frame.grid_columnconfigure(4, weight=1)
process_button = ctk.CTkButton(bottom_frame, text='Process', command=lambda: process(casedata))
process_button.grid(row=0, column=0, rowspan=2, padx=5)
close_button = ctk.CTkButton(bottom_frame, text='Close', command=main_window.quit)
close_button.grid(row=0, column=1, rowspan=2, padx=5)
# Use padding for separator effect
case_data_button = ctk.CTkButton(bottom_frame, text='Case Data', command=case_data)
case_data_button.grid(row=0, column=3, rowspan=2, padx=(10,5)) # Add left padding
# Use padding for separator effect
selected_modules_label = ctk.CTkLabel(bottom_frame, text='Number of selected modules: ')
selected_modules_label.grid(row=0, column=5, padx=(10,5), sticky='e') # Add left padding
auto_unselected_modules_text = '(Modules making some time to run were automatically unselected)'
auto_unselected_modules_label = ctk.CTkLabel(
    bottom_frame,
    text=auto_unselected_modules_text,
    font=ctk.CTkFont(family='Helvetica', size=10))
auto_unselected_modules_label.grid(row=1, column=5, padx=5, sticky='e')
get_selected_modules()

#### Logs
logtext_frame = ctk.CTkFrame(main_window)
logtext_frame.grid_columnconfigure(0, weight=1)
log_text = ctk.CTkTextbox(
    logtext_frame, height=log_text_height * 15) # Approx height based on lines
log_text.grid(row=0, column=0, padx=4, pady=10, sticky='we')

### Progress bar
progress_bar = ctk.CTkProgressBar(main_window, orientation='horizontal')

### Push main window on top
def OnFocusIn(event):
    if isinstance(event.widget, ctk.CTk): # Check if the widget is a CustomTkinter root window
        event.widget.attributes('-topmost', False)

main_window.attributes('-topmost', True)
main_window.focus_force()
main_window.bind('<FocusIn>', OnFocusIn)
lava_only_artifacts = False # Placeholder as this variable was not defined in the original snippet

main_window.mainloop()
