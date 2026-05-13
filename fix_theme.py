import os

folder_name = ".streamlit"
if not os.path.exists(folder_name):
    os.makedirs(folder_name)

# Here is the new Dark Blue & Grey theme!
theme_code = """[theme]
# The main accent color (Cool Grey)
primaryColor = "#8e9aaf" 

# The main background (Deep Dark Blue)
backgroundColor = "#081c34" 

# The sidebar and popover background (Slightly lighter Grey-Blue)
secondaryBackgroundColor = "#152a45" 

# The text color (Pure White so it pops against the dark blue)
textColor = "#ffffff" 

font = "sans serif"
"""

file_path = os.path.join(folder_name, "config.toml")
with open(file_path, "w") as f:
    f.write(theme_code)

print("✅ Dark Mode config.toml successfully written!")