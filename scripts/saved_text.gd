class_name SavedText
extends RefCounted
## Replace a small text file only after its complete contents are on disk.

static func replace(path: String, contents: String) -> Error:
	if path.begins_with("res://") and not OS.has_feature("editor"):
		return ERR_FILE_CANT_WRITE
	var target := ProjectSettings.globalize_path(path)
	var temporary := "%s.%d.%d.tmp" % [target, OS.get_process_id(), ResourceUID.create_id()]
	var file := FileAccess.open(temporary, FileAccess.WRITE)
	if file == null:
		return FileAccess.get_open_error()
	var written := file.store_string(contents)
	file.close()
	# A buffered write can still fail when the stream closes (for example, a full disk).
	var check := FileAccess.open(temporary, FileAccess.READ)
	var complete := written and check != null and check.get_as_text() == contents
	check = null
	var err := DirAccess.rename_absolute(temporary, target) if complete else ERR_FILE_CANT_WRITE
	if err != OK:
		DirAccess.remove_absolute(temporary)
	return err
