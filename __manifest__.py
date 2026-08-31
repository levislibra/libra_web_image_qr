{
    "name": "Libra Web Image QR",
    "summary": "Carga campos de imagen desde un teléfono mediante un código QR",
    "version": "16.0.1.0.0",
    "category": "Productivity",
    "author": "Librasoft",
    "website": "https://www.libra-soft.com",
    "license": "LGPL-3",
    "depends": ["web", "bus"],
    "data": [
        "security/ir.model.access.csv",
        "security/image_upload_security.xml",
        "views/image_qr_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "libra_web_image_qr/static/src/js/image_qr_field.js",
            "libra_web_image_qr/static/src/xml/image_qr_field.xml",
            "libra_web_image_qr/static/src/scss/image_qr_field.scss",
        ],
    },
    "installable": True,
    "application": False,
}
