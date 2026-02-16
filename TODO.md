
# Features

- Add a packaging/install builder.
- Add a script that enables to add or remove a string from the name of the selected files.

# Bugs

- Settings button should not be grayd out when waiting for an image processing, it prevents from viewing the log.

- Missing server :
  - Launch a comfy image processing with no server up
  - Log output : "Enhance failed: <urlopen error [Errno 111] Connexion refusée>"
  - Start the comfy server
  - Launch an image processing (the Go button is NOT grayed out)
  - Log output : "Enhance failed: Enhance already running."
  - Restart Krita
  - Image processing works
We shouldn't have to restart Krita, "Enhance failed: Enhance already running." is abnormal in this case.
