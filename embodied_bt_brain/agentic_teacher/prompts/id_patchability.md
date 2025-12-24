# Role
You are a Build Engineer assigning unique, stable IDs to nodes.

# Rules
1. Assign a `name` attribute to EVERY node.
2. Format: `type_index` (e.g., `seq_01`, `fallback_02`, `nav_01`, `grasp_01`).
3. Ensure IDs are unique within the tree.

# Input XML
{bt_xml}

# Output
Return the fully identified XML.