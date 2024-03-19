#!/usr/bin/python3
import os
import subprocess
import json
import datetime
import yaml
import sys
import argparse


class ConfigLoader:
    def __init__(self, config_path="~/.config/yabai/resize_ultrawide/config.yml"):
        self.config_path = os.path.expanduser(config_path)
        self.config = self.load_config()

    def load_config(self):
        """Load the YAML configuration file."""
        with open(self.config_path, 'r') as file:
            return yaml.safe_load(file)

    def save_config(self):
        """Save the current configuration to the YAML file."""
        with open(self.config_path, 'w') as file:
            yaml.safe_dump(self.config, file, default_flow_style=False)

    def update_yaml_key(self, keys_path, new_value):
        """Update a specific key in the configuration and save the changes."""
        
        # Navigate through the nested dictionaries except for the last key
        temp = self.config
        for key in keys_path[:-1]:
            temp = temp.get(key, {})  # Ensure nested dictionaries exist
        
        # Update the value for the last key
        temp[keys_path[-1]] = new_value
        
        # Save the updated configuration back to the file
        self.save_config()



class App_Manager:
    def __init__(self, config_loader):
        # Assuming config_loader is an instance of a class that has .config for accessing
        # the configuration dictionary and a method for updating it.
        self.config_loader = config_loader


    def create_notification(self, title, message):
        """Create a notification on macOS."""
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script])

    def toggle_setting(self, keys_path):
        """Toggle an on/off state of a setting in the config by reversing its current value."""
        config = self.config_loader.config  # Access the current configuration
        current_setting = config

        for key in keys_path[:-1]:
            current_setting = current_setting.setdefault(key, {})  # This ensures the path exists

        last_key = keys_path[-1]
        current_value = current_setting.get(last_key, None)

        # Determine the new value by reversing the current one
        if current_value is not None:
            new_value = not current_value
            self.config_loader.update_yaml_key(keys_path, new_value)
            return "On" if new_value else "Off"
        else:
            print(f"Warning: Setting {'.'.join(keys_path)} not found in the config.")

    def toggle_screen_management(self):
        """This method's implementation depends on the structure of your config and how screens are managed."""
        # Implementation depends on the details of your config structure
        current_space = Resize.get_current_space()
        onoff = self.toggle_setting(["space", f's_{current_space}', "managed"])
        self.create_notification("Yabai Resizer Management", f"Space {current_space} {onoff}.")

class Resize:
    def __init__(self, config_loader):
        ### Loading config file
        yabai_resize_dir = os.path.expanduser("~/.config/yabai/resize_ultrawide")
        self.config = config_loader.config
        self.log_file = os.path.expanduser(f'{yabai_resize_dir}/{self.config["log_file"]}')
        self.debug = self.config["debug"]

    def log(self, message):
        with open(self.log_file, "a") as log:
            log.write(f"{message}\n")

    @staticmethod
    def get_current_space():
        current_space_json = subprocess.run(["yabai", "-m", "query", "--spaces", "--space"], capture_output=True, text=True).stdout
        return json.loads(current_space_json)['index']

    def get_window_count(self):
        window_count_json = json.loads(subprocess.run(["yabai", "-m", "query", "--windows", "--space"], capture_output=True, text=True).stdout)



        # Remove blacklisted windows from the config
        windows_to_remove = []
        # Check against each exclusion criteria
        for i in window_count_json:  # Iterate over the original list
            for criteria, values in self.config["windows_blacklist"].items():
                # Perform case-insensitive comparison if necessary
                if criteria in i and any(val.lower() == i[criteria].lower() for val in values):
                    windows_to_remove.append(i)
                    self.log(f"Marked for removal {criteria}: {i[criteria]} window.")

        # Remove marked windows
        for window in windows_to_remove:
            window_count_json.remove(window)
            self.log(f"Removed {window[criteria]} window.")

        # Log final window count
        final_count = len(window_count_json)

        return final_count


                
    def get_newest_window(self):
        try:
            # Querying all windows for the current space or all spaces if needed
            current_space = str(self.get_current_space())
            result = subprocess.run(["yabai", "-m", "query", "--windows", "--space", current_space], capture_output=True, text=True)
            # Parse the JSON output
            windows = json.loads(result.stdout)
            
            # Find the window with the highest ID
            if windows:
                newest_window = max(windows, key=lambda x: x["id"])
                if self.debug:
                    self.log(f"---Newest window---")
                    self.log(f"Newest window ID: {newest_window['id']}")
                    self.log(f"Newest app: {newest_window['app']}")
                    self.log(f"Newest title: {newest_window['title']}")
                    self.log(f"Newest role: {newest_window['role']}")
                    self.log(f"Newest subrole: {newest_window['subrole']}")
                    self.log(f"---End of newest window---")
                return newest_window["id"]
            else:
                print("No windows found.")
                return None
        except Exception as e:
            print(f"Error querying windows: {e}")
            return None

    def get_height_of_window(self, window_id):
        try:
            result = subprocess.run(["yabai", "-m", "query", "--windows", "--window", str(window_id)], capture_output=True, text=True)
            window = json.loads(result.stdout)
            return window["frame"]["h"]
            self.log(f"Window height: {window['frame']['h']}")
        except Exception as e:
            print(f"Error querying window height: {e}")
            return None
    
    def apply_padding(self, left, right):
        current_space = str(self.get_current_space())
        subprocess.run(["yabai", "-m", "config", "--space", current_space, "left_padding", str(left)])
        subprocess.run(["yabai", "-m", "config", "--space", current_space, "right_padding", str(right)])


    def find_managed_display(self):
        results = subprocess.run(["yabai", "-m", "query", "--displays"], capture_output=True, text=True)
        displays = json.loads(results.stdout)
        managed_displays = self.config["displays"]

        # Iterate over each display returned by the yabai query
        for yabai_display_query in displays:
            # Iterate over each managed display in the configuration
            for display_name, config in managed_displays.items():
                if yabai_display_query["uuid"] == config["uuid"]:
                    return display_name, yabai_display_query
        return None, None  # Return None if no managed display is found
    
    def get_padding(self, current_display, window_count):
        try:
            screen_count_padding = self.config["displays"][current_display][f'window_count_{window_count}'][str("padding")]
            default_padding = str(self.config["displays"][current_display]['default_padding'])
            if screen_count_padding == "default_padding":
                screen_count_padding = default_padding
            return screen_count_padding, default_padding
        except KeyError as e:
            self.log(f"Configuration error for padding key {e}. exiting.")
            sys.exit()

    def space_manage_bool(self, current_space):
        try: 
            if not self.config['space'][f's_{current_space}']['managed']:
                return False
        except:
            self.log(f"Space s_{current_space} has no manage flag in the config file.")
            return False
        return True

    def resize_windows(self):
        if not self.config.get('managed'):
            self.log("Global management is turned off, not modifying padding.")
            sys.exit()

        current_space = self.get_current_space()
        window_count = self.get_window_count()

        current_display, yabai_display_query = self.find_managed_display()
        if current_display is None:
            self.log("No managed display found. exiting.")
            sys.exit()


        if int(window_count) >= self.config["displays"][current_display]['stop_manage_at']:
            self.log(f"Window count exceeds what is defined to manage in config for {current_display}. default yabai settings.")
            return

        screen_count_padding, default_padding = self.get_padding(current_display, window_count)


        if not self.space_manage_bool(current_space):
            self.log(f"Applying default padding {str(default_padding)} due to unmanage flag on window.")
            self.apply_padding(default_padding, default_padding)
            return
        print()
        
        self.log(f"Applying {str(screen_count_padding)} padding due to {window_count} windows.")
        self.apply_padding(default_padding, screen_count_padding)


        if self.config["displays"][current_display].get(f'window_count_{window_count}', {}).get('flip', False):
            # get id of just spawned window
            newest_window = self.get_newest_window()
            window_vertical_bool = self.get_height_of_window(newest_window) > int(yabai_display_query["frame"]["h"]) * 0.9 # 90% of the screen height
            if not window_vertical_bool:
                self.log("Window is not vertical, not toggling split.")
                subprocess.run(["yabai", "-m", "window" , "--toggle", "split"]) 

    def run(self):
        now = datetime.datetime.now()
        self.log(f'------------- {now.strftime("%m-%d %H:%M:%S")} -------------')
        self.log(f"Current global management: {self.config.get('managed')}")
        self.resize_windows()
        if self.debug:
            self.get_newest_window()

def main():
    config_loader = ConfigLoader()  # Load the config once
    resize_instance = Resize(config_loader)

    parser = argparse.ArgumentParser(description="Manage my application.")
    parser.add_argument('-r', '--resize', action='store_true', help='Resize specified windows or spaces')
    parser.add_argument('--toggle_manage', action='store_true', help='Toggle an on/off global management.')
    parser.add_argument('--toggle_manage_space', action='store_true', help='Toggle an on/off current space management.')
    # Add more arguments as needed

    args = parser.parse_args()

    if args.toggle_manage or args.toggle_manage_space:
        app_manager_instance = App_Manager(config_loader)
        if args.toggle_manage:
            onoff = app_manager_instance.toggle_setting(["managed"])
            app_manager_instance.create_notification("Yabai Resizer Management", f"Global Management {onoff}.")
        if args.toggle_manage_space:
            app_manager_instance.toggle_screen_management()
        resize_instance.run()

    if args.resize:
        resize_instance.run()
    


if __name__ == "__main__":
    main()