# BBD's Krita Script Starter Feb 2018

from krita import Extension
from krita import Krita, Selection
from PyQt5.QtGui import QImage

EXTENSION_ID = 'pykrita_select_face'
MENU_ENTRY = 'Select face'

DOWNSCALE_SIZE = 128
SELECTION_WIDTH = 1024
SELECTION_HEIGHT = 1024
LUMINANCE_THRESHOLD = 60
VERTICAL_CROP_RATIO = 0.85

class Select_face(Extension):

    def blob_score(self, blob):
        xs = [pt[0] for pt in blob]
        ys = [pt[1] for pt in blob]
        w = max(xs) - min(xs) + 1
        h = max(ys) - min(ys) + 1
        area = len(blob)
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)

        vertical_center = cy / DOWNSCALE_SIZE
        vertical_score = 1.0 - abs(vertical_center - 0.4)

        aspect = w / h if h != 0 else 0
        form_score = 1.0 if 0.5 <= aspect <= 2.0 else 0.5

        return area * vertical_score * form_score

    def detect_face_and_select(self):
        app = Krita.instance()
        doc = app.activeDocument()
        if not doc:
            print("❌ Aucun document ouvert.")
            return

        orig_w = doc.width()
        orig_h = doc.height()

        # Générer une image aplatie
        projection = doc.projection(0, 0, orig_w, orig_h)
        projection = projection.scaled(DOWNSCALE_SIZE, DOWNSCALE_SIZE)
        projection = projection.convertToFormat(QImage.Format_RGBA8888)

        ptr = projection.bits()
        ptr.setsize(projection.byteCount())
        raw_bytes = bytearray(ptr.asstring())

        # Créer un calque temporaire dans le document actif
        temp_layer = doc.createNode("face_downscale", "paintLayer")
        doc.rootNode().addChildNode(temp_layer, None)
        temp_layer.setPixelData(raw_bytes, 0, 0, DOWNSCALE_SIZE, DOWNSCALE_SIZE)

        # Lire les pixels
        raw = temp_layer.pixelData(0, 0, DOWNSCALE_SIZE, DOWNSCALE_SIZE)
        img = bytearray(raw if isinstance(raw, (bytearray, bytes)) else raw.data())

        if len(img) < DOWNSCALE_SIZE * DOWNSCALE_SIZE * 4:
            print("❌ Données incomplètes. setPixelData a échoué.")
            doc.rootNode().removeChildNode(temp_layer)
            return

        luma = []
        for y in range(DOWNSCALE_SIZE):
            row = []
            for x in range(DOWNSCALE_SIZE):
                offset = (y * DOWNSCALE_SIZE + x) * 4
                r, g, b = img[offset], img[offset+1], img[offset+2]
                lum = int(0.3 * r + 0.59 * g + 0.11 * b)
                row.append(lum)
            luma.append(row)

        # Boost de contraste
        for y in range(DOWNSCALE_SIZE):
            for x in range(DOWNSCALE_SIZE):
                l = luma[y][x]
                if l < 64:
                    luma[y][x] = 0
                elif l > 192:
                    luma[y][x] = 255
                else:
                    luma[y][x] = int((l - 64) * 255 / (192 - 64))

        binary = [[1 if luma[y][x] > LUMINANCE_THRESHOLD else 0 for x in range(DOWNSCALE_SIZE)] for y in range(DOWNSCALE_SIZE)]
        crop_h = int(DOWNSCALE_SIZE * VERTICAL_CROP_RATIO)
        binary_crop = [row[:DOWNSCALE_SIZE] for row in binary[:crop_h]]

        visited = [[False for _ in range(DOWNSCALE_SIZE)] for _ in range(crop_h)]
        blobs = []

        for y in range(crop_h):
            for x in range(DOWNSCALE_SIZE):
                if binary_crop[y][x] == 1 and not visited[y][x]:
                    queue = [(x, y)]
                    visited[y][x] = True
                    coords = [(x, y)]
                    while queue:
                        cx, cy = queue.pop()
                        for dx in [-1, 0, 1]:
                            for dy in [-1, 0, 1]:
                                nx, ny = cx + dx, cy + dy
                                if 0 <= nx < DOWNSCALE_SIZE and 0 <= ny < crop_h:
                                    if binary_crop[ny][nx] == 1 and not visited[ny][nx]:
                                        visited[ny][nx] = True
                                        queue.append((nx, ny))
                                        coords.append((nx, ny))
                    blobs.append(coords)

        if not blobs:
            doc.rootNode().removeChildNode(temp_layer)
            return

        largest = max(blobs, key=self.blob_score)
        xs = sorted([pt[0] for pt in largest])
        ys = sorted([pt[1] for pt in largest])
        cx = xs[len(xs) // 2]
        cy = int(ys[0] + 0.75 * (ys[-1] - ys[0]))

        scale_x = orig_w / DOWNSCALE_SIZE
        scale_y = orig_h / DOWNSCALE_SIZE
        cx_full = int(cx * scale_x)
        cy_full = int(cy * scale_y)

        sel_x = cx_full - SELECTION_WIDTH // 2
        sel_y = cy_full - SELECTION_HEIGHT // 2

        sel_x = max(0, min(sel_x, orig_w - SELECTION_WIDTH))
        sel_y = max(0, min(sel_y, orig_h - SELECTION_HEIGHT))

        selection = Selection()
        selection.select(sel_x, sel_y, SELECTION_WIDTH, SELECTION_HEIGHT, 1)
        doc.setSelection(selection)

        # Nettoyage
        doc.rootNode().removeChildNode(temp_layer)

    def __init__(self, parent):
        # Always initialise the superclass.
        # This is necessary to create the underlying C++ object
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction(EXTENSION_ID, MENU_ENTRY, "tools/scripts")
        # parameter 1 = the name that Krita uses to identify the action
        # parameter 2 = the text to be added to the menu entry for this script
        # parameter 3 = location of menu entry
        action.triggered.connect(self.action_triggered)

    def action_triggered(self):
        self.detect_face_and_select()
        # pass
