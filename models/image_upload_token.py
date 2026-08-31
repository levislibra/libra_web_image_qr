import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class ImageUploadToken(models.Model):
    _name = "libra.image.upload.token"
    _description = "Enlace temporal para cargar una imagen"
    _order = "create_date desc"

    token = fields.Char(required=True, readonly=True, index=True, copy=False)
    model_name = fields.Char(required=True, readonly=True)
    res_id = fields.Integer(required=True, readonly=True)
    field_name = fields.Char(required=True, readonly=True)
    expires_at = fields.Datetime(required=True, readonly=True)
    uploaded = fields.Boolean(default=False, readonly=True)
    uploaded_at = fields.Datetime(readonly=True)

    _sql_constraints = [
        ("token_unique", "unique(token)", "El token de carga debe ser único."),
    ]

    @api.model
    def create_upload_url(self, model_name, res_id, field_name):
        if not model_name or not res_id or not field_name:
            raise UserError(_("Guarde el registro antes de generar el código QR."))

        if model_name not in self.env:
            raise ValidationError(_("El modelo solicitado no existe."))
        model = self.env[model_name]
        field = model._fields.get(field_name)
        if not field or field.type != "binary":
            raise ValidationError(_("El campo solicitado no es una imagen binaria."))

        record = model.browse(int(res_id)).exists()
        if not record:
            raise UserError(_("El registro ya no existe."))
        record.check_access_rights("write")
        record.check_access_rule("write")

        existing_token = self.search([
            ("create_uid", "=", self.env.uid),
            ("model_name", "=", model_name),
            ("res_id", "=", record.id),
            ("field_name", "=", field_name),
            ("uploaded", "=", False),
            ("expires_at", ">", fields.Datetime.now()),
        ], limit=1)
        if existing_token:
            return existing_token._upload_result()

        self.search([
            ("create_uid", "=", self.env.uid),
            ("model_name", "=", model_name),
            ("res_id", "=", record.id),
            ("field_name", "=", field_name),
            ("uploaded", "=", False),
        ]).unlink()

        upload_token = self.create({
            "token": secrets.token_urlsafe(32),
            "model_name": model_name,
            "res_id": record.id,
            "field_name": field_name,
            "expires_at": fields.Datetime.now() + timedelta(minutes=15),
        })
        return upload_token._upload_result()

    def _upload_result(self):
        self.ensure_one()
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url").rstrip("/")
        return {
            "token": self.token,
            "upload_url": "%s/image-qr/upload/%s" % (base_url, self.token),
            "qr_url": "/image-qr/code/%s" % self.token,
        }

    @api.model
    def upload_status(self, token):
        upload_token = self.search([
            ("token", "=", token),
            ("create_uid", "=", self.env.uid),
        ], limit=1)
        return {"uploaded": bool(upload_token.uploaded)}

    @api.autovacuum
    def _gc_expired_tokens(self):
        self.search([("expires_at", "<", fields.Datetime.now())]).unlink()

    def _is_available(self):
        self.ensure_one()
        return not self.uploaded and self.expires_at >= fields.Datetime.now()

    def _write_image(self, image_base64):
        self.ensure_one()
        if not self._is_available():
            raise AccessError(_("Este enlace de carga venció o ya fue utilizado."))
        model = self.env[self.model_name] if self.model_name in self.env else None
        field = model._fields.get(self.field_name) if model is not None else None
        record = model.browse(self.res_id).exists() if model is not None else model
        if not field or field.type != "binary" or not record:
            raise ValidationError(_("El destino de la imagen ya no está disponible."))
        record.sudo().write({self.field_name: image_base64})
        self.sudo().write({
            "uploaded": True,
            "uploaded_at": fields.Datetime.now(),
        })
        self.env["bus.bus"]._sendone(
            "libra_image_qr:%s" % self.token,
            "libra_image_qr.uploaded",
            {"token": self.token},
        )
