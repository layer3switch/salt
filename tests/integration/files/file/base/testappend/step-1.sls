{{ salt['runtests_helpers.get_salt_temp_dir_for_path']('test.append') }}:

  file.append:
    - source: salt://testappend/firstif
