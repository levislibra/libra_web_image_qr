/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ImageField } from "@web/views/fields/image/image_field";
import { onWillUnmount, useState } from "@odoo/owl";

export class ImageQrField extends ImageField {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this.qrState = useState({
            loading: false,
            qrUrl: false,
            token: false,
            cacheBuster: false,
        });
        this.qrChannel = null;
        this.onBusNotification = this.onBusNotification.bind(this);
        this.busService.addEventListener("notification", this.onBusNotification);
        onWillUnmount(() => {
            this.busService.removeEventListener("notification", this.onBusNotification);
            if (this.qrChannel) {
                this.busService.deleteChannel(this.qrChannel);
            }
        });
    }

    async showQr() {
        if (this.props.readonly || this.qrState.loading || this.qrState.qrUrl) {
            return;
        }
        if (!this.props.record.resId) {
            this.notification.add("Guarde el registro antes de cargar una imagen por QR.", {
                type: "warning",
            });
            return;
        }
        this.qrState.loading = true;
        try {
            const result = await this.orm.call(
                "libra.image.upload.token",
                "create_upload_url",
                [],
                {
                    model_name: this.props.record.resModel,
                    res_id: this.props.record.resId,
                    field_name: this.props.name,
                }
            );
            this.qrState.token = result.token;
            this.qrChannel = `libra_image_qr:${result.token}`;
            await this.busService.addChannel(this.qrChannel);
            this.qrState.qrUrl = result.qr_url;
        } catch (error) {
            this.notification.add(error.message || "No se pudo generar el código QR.", {
                type: "danger",
            });
        } finally {
            this.qrState.loading = false;
        }
    }

    async onBusNotification({ detail: notifications }) {
        for (const { payload, type } of notifications) {
            if (type === "libra_image_qr.uploaded" && payload.token === this.qrState.token) {
                if (this.qrChannel) {
                    this.busService.deleteChannel(this.qrChannel);
                    this.qrChannel = null;
                }
                this.qrState.qrUrl = false;
                this.qrState.token = false;
                this.lastURL = undefined;
                await this.props.record.load();
                this.qrState.cacheBuster = Date.now();
                this.notification.add("La imagen se cargó correctamente.", { type: "success" });
                break;
            }
        }
    }

    async refreshImage() {
        this.lastURL = undefined;
        this.state.isValid = true;
        await this.props.record.load();
        this.qrState.cacheBuster = Date.now();
        this.notification.add("La imagen fue actualizada.", { type: "success" });
    }

    getUrl(previewFieldName) {
        const imageUrl = super.getUrl(previewFieldName);
        if (this.qrState.cacheBuster && imageUrl.startsWith("/web/image")) {
            const separator = imageUrl.includes("?") ? "&" : "?";
            return `${imageUrl}${separator}libra_qr=${this.qrState.cacheBuster}`;
        }
        return imageUrl;
    }
}

ImageQrField.template = "libra_web_image_qr.ImageField";

registry.category("fields").add("image", ImageQrField, { force: true });
registry.category("fields").add("kanban.image", ImageQrField, { force: true });
