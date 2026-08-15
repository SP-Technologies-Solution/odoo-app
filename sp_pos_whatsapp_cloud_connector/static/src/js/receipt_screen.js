import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";

patch(ReceiptScreen.prototype, {
    async actionSendReceiptOnWhatsApp() {
        const order = this.currentOrder;
        if (typeof order.id !== "number") {
            this.notification.add(
                _t("The order is not synced to the server yet. Please wait a moment and try again."),
                { type: "warning" }
            );
            return;
        }
        try {
            await this.pos.data.call("pos.order", "action_send_whatsapp_receipt", [
                [order.id],
                this.state.phone || false,
            ]);
            this.notification.add(_t("Receipt sent on WhatsApp."), { type: "success" });
        } catch (error) {
            const message =
                error?.data?.message || error?.message || _t("Could not send the receipt on WhatsApp.");
            this.notification.add(message, { type: "danger" });
        }
    },
});
