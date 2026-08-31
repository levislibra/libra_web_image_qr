import base64
import io

import qrcode
from PIL import Image, UnidentifiedImageError

from odoo import http
from odoo.http import request
from werkzeug.exceptions import NotFound


MAX_IMAGE_SIZE = 15 * 1024 * 1024
ALLOWED_MIMETYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


class ImageQrUploadController(http.Controller):
    def _get_token(self, token):
        upload_token = request.env["libra.image.upload.token"].sudo().search([
            ("token", "=", token),
        ], limit=1)
        if not upload_token:
            raise NotFound()
        return upload_token

    @http.route("/image-qr/code/<string:token>", type="http", auth="public", sitemap=False)
    def image_qr_code(self, token, **kwargs):
        upload_token = self._get_token(token)
        if not upload_token._is_available():
            raise NotFound()
        base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url").rstrip("/")
        upload_url = "%s/image-qr/upload/%s" % (base_url, token)
        qr_image = qrcode.make(upload_url)
        output = io.BytesIO()
        qr_image.save(output, format="PNG")
        return request.make_response(output.getvalue(), headers=[
            ("Content-Type", "image/png"),
            ("Cache-Control", "no-store"),
        ])

    @http.route(
        "/image-qr/upload/<string:token>",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
        sitemap=False,
    )
    def image_qr_upload(self, token, **post):
        upload_token = self._get_token(token)
        error = None
        success = False

        if request.httprequest.method == "POST":
            image = request.httprequest.files.get("image")
            if not upload_token._is_available():
                error = "Este enlace ya fue utilizado. Genere un nuevo QR desde Odoo."
            elif not image or not image.filename:
                error = "Seleccione una imagen o tome una foto."
            elif image.mimetype not in ALLOWED_MIMETYPES:
                error = "Formato no permitido. Use JPG, PNG, GIF o WebP."
            else:
                content = image.read(MAX_IMAGE_SIZE + 1)
                if len(content) > MAX_IMAGE_SIZE:
                    error = "La imagen supera el límite de 15 MB."
                elif not content:
                    error = "La imagen está vacía."
                else:
                    try:
                        Image.open(io.BytesIO(content)).verify()
                    except (UnidentifiedImageError, OSError, ValueError):
                        error = "El archivo no contiene una imagen válida."
                    else:
                        upload_token._write_image(base64.b64encode(content))
                        success = True

        return request.render("libra_web_image_qr.image_upload_page", {
            "upload_token": upload_token,
            "error": error,
            "success": success,
        })
