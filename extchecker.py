import os

def get_unique_extensions(directory):
    extensions = set()
    
    for root, _, files in os.walk(directory):
        for file in files:
            _, ext = os.path.splitext(file)
            if ext:
                extensions.add(ext.lower())
    
    return extensions

def write_extensions_to_file(extensions, file_path):
    with open(file_path, 'w') as file:
        for ext in sorted(extensions):
            file.write(f"{ext}\n")

directory = 'Y:\\Musicals\\!processing'  # Replace with your directory path
output_file = 'unique_extensions.txt'  # Replace with your desired output file path

unique_extensions = get_unique_extensions(directory)
write_extensions_to_file(unique_extensions, output_file)

print(f"Unique file extensions have been written to {output_file}")
