/tmp/salttest/issue-1879:
      
  file.append:
    - text: |
        # set variable identifying the chroot you work in (used in the prompt below)
        if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
            debian_chroot=$(cat /etc/debian_chroot)
        fi