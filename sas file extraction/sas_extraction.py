import pyreadstat
import json

def create_por_metadata_dict(file_path):
    df, metadata = pyreadstat.read_por(file_path)
    metadata_dict = {}

    for index, column_name in enumerate(metadata.column_names):
        column_info = {
            "column_name": column_name,
            "column_type": metadata.original_variable_types.get(column_name, "Unknown"),
            "column_label": metadata.column_labels[index] if index < len(metadata.column_labels) else "No label",
            "labelled_values": metadata.variable_value_labels.get(column_name, "No labelled values")
        }
        metadata_dict[column_name] = column_info

    return metadata_dict

# Replace 'path/to/your/file.por' with the actual path to your POR file
file_path = r"C:\Users\sag19\Downloads\31119822.por"

# Create the metadata dictionary
por_metadata = create_por_metadata_dict(file_path)

# Print the dictionary
print(json.dumps(por_metadata, indent=2))

# Optionally, you can save the dictionary to a JSON file
with open('por_metadata.json', 'w') as f:
    json.dump(por_metadata, f, indent=2)
