"""
FinGestor - App de contas a pagar e a receber (MVP).
UI em KivyMD; dados em SQLite (db.py); cupom em PNG/PDF (receipt.py).

Testavel no desktop:  python main.py
Empacotavel em APK:   via GitHub Actions (.github/workflows) ou `buildozer android debug`
"""
import os
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.window import Window

from kivymd.app import MDApp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.list import (
    ThreeLineListItem, TwoLineListItem, OneLineListItem, IconLeftWidget,
    TwoLineAvatarIconListItem,
)
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.snackbar import Snackbar
from kivy.properties import StringProperty


class StatCard(MDCard):
    value = StringProperty("")
    label = StringProperty("")

from db import Database, fmt_money, cents_from_str, STATUS_LABEL, today_iso
import receipt

# Janela confortavel no desktop (ignorado no Android)
if os.environ.get("KIVY_BUILD") != "android":
    Window.size = (400, 720)


KV = '''
#:import dp kivy.metrics.dp

<StatCard>:
    orientation: "vertical"
    padding: dp(14)
    radius: [16,]
    md_bg_color: app.theme_cls.primary_light
    size_hint_y: None
    height: dp(96)
    value: ""
    label: ""
    MDLabel:
        text: root.value
        font_style: "H6"
        bold: True
        adaptive_height: True
    MDLabel:
        text: root.label
        font_style: "Caption"
        theme_text_color: "Secondary"
        adaptive_height: True

ScreenManager:
    id: sm

    Screen:
        name: "main"
        MDBoxLayout:
            orientation: "vertical"
            MDTopAppBar:
                id: top_bar
                title: "FinGestor"
                elevation: 2
                right_action_items: [["refresh", lambda x: app.refresh_all()]]
            MDBottomNavigation:
                id: bottom_nav
                on_switch_tabs: app.on_tab_switch(*args)
                selected_color_background: app.theme_cls.primary_light
                text_color_active: app.theme_cls.primary_color

                MDBottomNavigationItem:
                    name: "tab_home"
                    text: "Inicio"
                    icon: "view-dashboard"
                    ScrollView:
                        MDBoxLayout:
                            id: dash_box
                            orientation: "vertical"
                            padding: dp(12)
                            spacing: dp(10)
                            adaptive_height: True

                MDBottomNavigationItem:
                    name: "tab_sales"
                    text: "Vendas"
                    icon: "cash-multiple"
                    MDBoxLayout:
                        orientation: "vertical"
                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(56)
                            padding: dp(8), 0
                            spacing: dp(6)
                            MDLabel:
                                text: "Filtro:"
                                size_hint_x: None
                                width: dp(52)
                                theme_text_color: "Secondary"
                            MDRaisedButton:
                                text: "Todas"
                                on_release: app.set_sales_filter("ALL")
                            MDFlatButton:
                                text: "Em aberto"
                                on_release: app.set_sales_filter("OPEN")
                            MDFlatButton:
                                text: "Atrasadas"
                                on_release: app.set_sales_filter("OVERDUE")
                        ScrollView:
                            MDList:
                                id: sales_list

                MDBottomNavigationItem:
                    name: "tab_contacts"
                    text: "Contatos"
                    icon: "account-multiple"
                    MDBoxLayout:
                        orientation: "vertical"
                        MDTextField:
                            id: contact_search
                            hint_text: "Buscar contato"
                            mode: "rectangle"
                            size_hint_x: 0.94
                            pos_hint: {"center_x": 0.5}
                            on_text: app.build_contacts()
                        ScrollView:
                            MDList:
                                id: contacts_list

                MDBottomNavigationItem:
                    name: "tab_settings"
                    text: "Ajustes"
                    icon: "cog"
                    ScrollView:
                        MDBoxLayout:
                            orientation: "vertical"
                            padding: dp(16)
                            spacing: dp(8)
                            adaptive_height: True
                            MDLabel:
                                text: "Dados da empresa/vendedor"
                                font_style: "H6"
                                adaptive_height: True
                            MDTextField:
                                id: co_name
                                hint_text: "Nome"
                            MDTextField:
                                id: co_document
                                hint_text: "CPF / CNPJ"
                            MDTextField:
                                id: co_phone
                                hint_text: "Telefone"
                            MDTextField:
                                id: co_email
                                hint_text: "E-mail"
                            MDTextField:
                                id: co_address
                                hint_text: "Endereco"
                            MDTextField:
                                id: co_currency
                                hint_text: "Simbolo da moeda"
                                text: "R$"
                            MDTextField:
                                id: co_footer
                                hint_text: "Rodape do cupom"
                            MDRaisedButton:
                                text: "Salvar"
                                pos_hint: {"center_x": 0.5}
                                on_release: app.save_company()

    Screen:
        name: "new_sale"
        MDBoxLayout:
            orientation: "vertical"
            MDTopAppBar:
                title: "Nova venda"
                left_action_items: [["arrow-left", lambda x: app.go_main("tab_sales")]]
            ScrollView:
                MDBoxLayout:
                    orientation: "vertical"
                    padding: dp(16)
                    spacing: dp(10)
                    adaptive_height: True
                    MDRaisedButton:
                        id: ns_client_btn
                        text: "Selecionar cliente"
                        on_release: app.open_client_picker()
                    MDTextField:
                        id: ns_desc
                        hint_text: "Descricao (opcional)"
                    MDTextField:
                        id: ns_gross
                        hint_text: "Valor bruto (ex: 150,00)"
                        input_filter: None
                    MDBoxLayout:
                        adaptive_height: True
                        spacing: dp(8)
                        MDTextField:
                            id: ns_discount
                            hint_text: "Desconto"
                            text: "0"
                        MDRaisedButton:
                            id: ns_disc_type
                            text: "R$"
                            on_release: app.toggle_discount_type()
                            size_hint_x: None
                            width: dp(64)
                    MDBoxLayout:
                        adaptive_height: True
                        height: dp(48)
                        MDLabel:
                            text: "Parcelado?"
                            adaptive_height: True
                        MDCheckbox:
                            id: ns_installment
                            size_hint: None, None
                            size: dp(40), dp(40)
                            on_active: app.on_installment_toggle(self.active)
                    MDTextField:
                        id: ns_nparc
                        hint_text: "Numero de parcelas"
                        text: "1"
                        disabled: True
                        input_filter: "int"
                    MDLabel:
                        id: ns_preview
                        text: ""
                        theme_text_color: "Secondary"
                        adaptive_height: True
                    MDRaisedButton:
                        text: "Registrar venda"
                        pos_hint: {"center_x": 0.5}
                        on_release: app.save_sale()

    Screen:
        name: "sale_detail"
        MDBoxLayout:
            orientation: "vertical"
            MDTopAppBar:
                title: "Detalhe da venda"
                left_action_items: [["arrow-left", lambda x: app.go_main("tab_sales")]]
            ScrollView:
                MDBoxLayout:
                    id: detail_box
                    orientation: "vertical"
                    padding: dp(16)
                    spacing: dp(8)
                    adaptive_height: True
'''


class FinGestorApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Teal"
        self.theme_cls.accent_palette = "Amber"
        self.theme_cls.theme_style = "Light"
        self.title = "FinGestor"
        db_path = os.path.join(self.user_data_dir, "fingestor.db")
        self.db = Database(db_path)
        self.dialog = None
        self.selected_client_id = None
        self.discount_type = "FIXED"
        self.sales_filter = "ALL"
        self.current_sale_id = None
        self.root_widget = Builder.load_string(KV)
        return self.root_widget

    def on_start(self):
        self.build_dashboard()
        self.build_sales()
        self.build_contacts()
        self.load_company_form()

    TAB_TITLES = {
        "tab_home": "Inicio", "tab_sales": "Vendas",
        "tab_contacts": "Contatos", "tab_settings": "Configuracoes",
    }

    def on_tab_switch(self, *args):
        # Assinatura varia entre versoes; procuramos o nome da aba nos argumentos
        name = None
        for a in args:
            if isinstance(a, str) and a in self.TAB_TITLES:
                name = a
                break
        if name is None:
            for a in args:
                n = getattr(a, "name", None)
                if n in self.TAB_TITLES:
                    name = n
                    break
        if name:
            self.set_title(self.TAB_TITLES[name])
        if name == "tab_home":
            self.build_dashboard()
        elif name == "tab_sales":
            self.build_sales()
        elif name == "tab_contacts":
            self.build_contacts()
        elif name == "tab_settings":
            self.load_company_form()

    # ---------------- utilitarios de UI ----------------
    def sm(self):
        return self.root_widget

    def set_title(self, t):
        self.root_widget.ids.top_bar.title = t

    def toast(self, msg):
        try:
            Snackbar(text=msg).open()
        except Exception:
            print("TOAST:", msg)

    def go_main(self, tab=None):
        self.root_widget.current = "main"
        if tab:
            self.root_widget.ids.bottom_nav.switch_tab(tab)
        self.refresh_all()

    def refresh_all(self, *_):
        self.build_dashboard()
        self.build_sales()
        self.build_contacts()

    def close_dialog(self, *_):
        if self.dialog:
            self.dialog.dismiss()
            self.dialog = None

    # ---------------- Dashboard ----------------
    def build_dashboard(self, *_):
        box = self.root_widget.ids.dash_box
        box.clear_widgets()
        recv = self.db.total_receivable()
        overdue = self.db.total_overdue()
        month = self.db.received_this_month()

        grid = MDBoxLayout(orientation="vertical", spacing=dp(10),
                           adaptive_height=True)

        def card(value, label, bg):
            c = StatCard()
            c.value = value
            c.label = label
            c.md_bg_color = bg
            return c

        grid.add_widget(card(fmt_money(recv), "A receber (em aberto)", (0.90, 0.97, 0.95, 1)))
        grid.add_widget(card(fmt_money(overdue), "Vencido / atrasado", (0.99, 0.92, 0.92, 1)))
        grid.add_widget(card(fmt_money(month), "Recebido no mes", (0.93, 0.96, 0.99, 1)))
        box.add_widget(grid)

        box.add_widget(MDLabel(text="Proximos vencimentos (7 dias)",
                               font_style="H6", adaptive_height=True))
        up = self.db.upcoming(days=7)
        if not up:
            box.add_widget(MDLabel(text="Nada a vencer nos proximos 7 dias.",
                                   theme_text_color="Secondary", adaptive_height=True))
        for i in up:
            open_c = i["amount_cents"] - i["paid_cents"]
            item = TwoLineListItem(
                text=f"{i['contact_name']}  -  {fmt_money(open_c)}",
                secondary_text=f"Venc. {i['due_date']}  [{STATUS_LABEL.get(i['status'],'')}]",
                on_release=lambda x, sid=i["sale_id"]: self.open_sale(sid),
            )
            box.add_widget(item)

    # ---------------- Vendas ----------------
    def set_sales_filter(self, f):
        self.sales_filter = f
        self.build_sales()

    def build_sales(self, *_):
        lst = self.root_widget.ids.sales_list
        lst.clear_widgets()
        lst.add_widget(OneLineListItem(
            text="+  Nova venda",
            on_release=lambda x: self.start_new_sale()))
        rows = self.db.list_sales()
        if self.sales_filter == "OPEN":
            rows = [r for r in rows if r["open_cents"] > 0]
        elif self.sales_filter == "OVERDUE":
            rows = [r for r in rows if r["status"] == "OVERDUE"]
        if not rows:
            lst.add_widget(OneLineListItem(text="Nenhuma venda ainda."))
        for r in rows:
            it = ThreeLineListItem(
                text=f"{r['contact_name']}  -  {fmt_money(r['net_cents'])}",
                secondary_text=f"{r['sale_date']}  |  {STATUS_LABEL.get(r['status'],'')}",
                tertiary_text=f"Em aberto: {fmt_money(r['open_cents'])}",
                on_release=lambda x, sid=r["id"]: self.open_sale(sid),
            )
            lst.add_widget(it)

    # ---------------- Nova venda ----------------
    def start_new_sale(self, *_):
        s = self.root_widget  # ids ficam no widget raiz
        self.selected_client_id = None
        self.discount_type = "FIXED"
        s.ids.ns_client_btn.text = "Selecionar cliente"
        s.ids.ns_desc.text = ""
        s.ids.ns_gross.text = ""
        s.ids.ns_discount.text = "0"
        s.ids.ns_disc_type.text = "R$"
        s.ids.ns_installment.active = False
        s.ids.ns_nparc.text = "1"
        s.ids.ns_nparc.disabled = True
        s.ids.ns_preview.text = ""
        self.root_widget.current = "new_sale"

    def on_installment_toggle(self, active):
        s = self.root_widget  # ids ficam no widget raiz
        s.ids.ns_nparc.disabled = not active
        if not active:
            s.ids.ns_nparc.text = "1"

    def toggle_discount_type(self):
        s = self.root_widget  # ids ficam no widget raiz
        self.discount_type = "PERCENT" if self.discount_type == "FIXED" else "FIXED"
        s.ids.ns_disc_type.text = "%" if self.discount_type == "PERCENT" else "R$"

    def open_client_picker(self):
        contacts = self.db.list_contacts()
        content = MDBoxLayout(orientation="vertical", adaptive_height=True,
                              spacing=dp(4), size_hint_y=None)
        content.height = dp(min(400, 56 * max(1, len(contacts) + 1)))
        from kivy.uix.scrollview import ScrollView
        from kivymd.uix.list import MDList
        ml = MDList()
        ml.add_widget(OneLineListItem(text="(Sem cliente)",
                      on_release=lambda x: self.pick_client(None, "Sem cliente")))
        for c in contacts:
            ml.add_widget(OneLineListItem(
                text=c["name"],
                on_release=lambda x, cid=c["id"], nm=c["name"]: self.pick_client(cid, nm)))
        sv = ScrollView()
        sv.add_widget(ml)
        content.add_widget(sv)
        self.dialog = MDDialog(title="Selecionar cliente", type="custom",
                               content_cls=content,
                               buttons=[MDFlatButton(text="Novo contato",
                                        on_release=lambda x: (self.close_dialog(),
                                                              self.open_contact_form())),
                                        MDFlatButton(text="Fechar",
                                        on_release=self.close_dialog)])
        self.dialog.open()

    def pick_client(self, cid, name):
        self.selected_client_id = cid
        self.root_widget.ids.ns_client_btn.text = name
        self.close_dialog()

    def save_sale(self):
        s = self.root_widget  # ids ficam no widget raiz
        gross = cents_from_str(s.ids.ns_gross.text)
        if gross <= 0:
            self.toast("Informe um valor bruto valido.")
            return
        if self.discount_type == "PERCENT":
            disc_val = cents_from_str(s.ids.ns_discount.text)  # ex 10 -> 1000 (=10,00%)
        else:
            disc_val = cents_from_str(s.ids.ns_discount.text)
        installment = s.ids.ns_installment.active
        try:
            n = int(s.ids.ns_nparc.text or "1")
        except ValueError:
            n = 1
        sale_id = self.db.create_sale(
            contact_id=self.selected_client_id,
            gross_cents=gross,
            discount_value_cents=disc_val,
            discount_type=self.discount_type,
            payment_type="INSTALLMENT" if installment else "CASH",
            n_installments=n,
            description=s.ids.ns_desc.text,
        )
        self.toast("Venda registrada!")
        self.open_sale(sale_id)

    # ---------------- Detalhe da venda ----------------
    def open_sale(self, sale_id):
        self.current_sale_id = sale_id
        self.render_sale_detail()
        self.root_widget.current = "sale_detail"

    def render_sale_detail(self):
        sale = self.db.get_sale(self.current_sale_id)
        box = self.root_widget.ids.detail_box
        box.clear_widgets()
        if not sale:
            box.add_widget(MDLabel(text="Venda nao encontrada."))
            return
        cname = sale["contact"]["name"] if sale["contact"] else "Sem cliente"
        box.add_widget(MDLabel(text=f"#{sale['id']:05d}  -  {cname}",
                               font_style="H6", adaptive_height=True))
        box.add_widget(MDLabel(text=f"Data: {sale['sale_date']}   |   "
                                    f"{STATUS_LABEL.get(sale['status'],'')}",
                               theme_text_color="Secondary", adaptive_height=True))
        box.add_widget(MDLabel(text=f"Subtotal: {fmt_money(sale['gross_cents'])}",
                               adaptive_height=True))
        if sale["discount_cents"] > 0:
            box.add_widget(MDLabel(text=f"Desconto: -{fmt_money(sale['discount_cents'])}",
                                   adaptive_height=True))
        box.add_widget(MDLabel(text=f"Total: {fmt_money(sale['net_cents'])}",
                               font_style="H6", adaptive_height=True))

        box.add_widget(MDLabel(text="Parcelas", font_style="Subtitle1",
                               adaptive_height=True))
        for i in sale["installments"]:
            st = Database.installment_status(i)
            open_c = i["amount_cents"] - i["paid_cents"]
            txt = f"{i['number']}/{len(sale['installments'])}  -  {fmt_money(i['amount_cents'])}"
            sec = f"Venc. {i['due_date']}  [{STATUS_LABEL.get(st,'')}]  aberto {fmt_money(open_c)}"
            item = TwoLineListItem(text=txt, secondary_text=sec)
            if open_c > 0:
                item.on_release = lambda x, iid=i["id"], oc=open_c: self.open_pay_dialog(iid, oc)
            box.add_widget(item)

        btns = MDBoxLayout(adaptive_height=True, spacing=dp(8), padding=(0, dp(12)))
        btns.add_widget(MDRaisedButton(text="Gerar cupom (PDF)",
                        on_release=lambda x: self.make_receipt("pdf")))
        btns.add_widget(MDRaisedButton(text="Imagem (PNG)",
                        on_release=lambda x: self.make_receipt("png")))
        box.add_widget(btns)

    def open_pay_dialog(self, installment_id, open_cents):
        field = MDTextField(hint_text="Valor da baixa",
                            text=f"{open_cents/100:.2f}".replace(".", ","))
        content = MDBoxLayout(orientation="vertical", adaptive_height=True,
                              size_hint_y=None, height=dp(90), padding=dp(8))
        content.add_widget(field)
        self.dialog = MDDialog(
            title="Dar baixa",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="Total",
                             on_release=lambda x: self.do_pay(installment_id, open_cents)),
                MDRaisedButton(text="Confirmar",
                               on_release=lambda x: self.do_pay(installment_id,
                                                                cents_from_str(field.text))),
                MDFlatButton(text="Cancelar", on_release=self.close_dialog),
            ],
        )
        self.dialog.open()

    def do_pay(self, installment_id, amount_cents):
        if amount_cents <= 0:
            self.toast("Valor invalido.")
            return
        self.db.pay_installment(installment_id, amount_cents)
        self.close_dialog()
        self.toast("Baixa registrada!")
        self.render_sale_detail()

    def make_receipt(self, fmt):
        sale = self.db.get_sale(self.current_sale_id)
        company = self.db.get_company()
        out_dir = os.path.join(self.user_data_dir, "cupons")
        try:
            paths = receipt.save_receipt(sale, company, out_dir, fmt=fmt)
        except Exception as e:
            self.toast(f"Erro ao gerar cupom: {e}")
            return
        path = paths.get(fmt) or next(iter(paths.values()))
        mime = "application/pdf" if fmt == "pdf" else "image/png"
        shared = receipt.share_file(path, mime=mime)
        if not shared:
            self.toast(f"Cupom salvo em: {path}")

    # ---------------- Contatos ----------------
    def build_contacts(self, *_):
        lst = self.root_widget.ids.contacts_list
        search = self.root_widget.ids.contact_search.text
        lst.clear_widgets()
        contacts = self.db.list_contacts(search=search)
        if not contacts:
            lst.add_widget(OneLineListItem(text="Nenhum contato. Use o botao Novo."))
        for c in contacts:
            tot = self.db.contact_totals(c["id"])
            it = TwoLineListItem(
                text=c["name"],
                secondary_text=f"{c.get('phone') or ''}  |  Devedor: {fmt_money(tot['owed_cents'])}",
                on_release=lambda x, cid=c["id"]: self.open_contact_form(cid),
            )
            lst.add_widget(it)
        lst.add_widget(OneLineListItem(text="+  Novo contato",
                       on_release=lambda x: self.open_contact_form()))

    def open_contact_form(self, cid=None):
        data = self.db.get_contact(cid) if cid else {}
        f_name = MDTextField(hint_text="Nome*", text=data.get("name", "") if data else "")
        f_phone = MDTextField(hint_text="Telefone", text=data.get("phone", "") if data else "")
        f_email = MDTextField(hint_text="E-mail", text=data.get("email", "") if data else "")
        f_doc = MDTextField(hint_text="CPF/CNPJ", text=data.get("document", "") if data else "")
        f_addr = MDTextField(hint_text="Endereco", text=data.get("address", "") if data else "")
        content = MDBoxLayout(orientation="vertical", adaptive_height=True,
                              size_hint_y=None, spacing=dp(4), padding=dp(4))
        for w in (f_name, f_phone, f_email, f_doc, f_addr):
            content.add_widget(w)
        content.height = dp(300)

        def save(*_):
            if not f_name.text.strip():
                self.toast("Nome obrigatorio.")
                return
            payload = dict(name=f_name.text.strip(), phone=f_phone.text,
                           email=f_email.text, document=f_doc.text, address=f_addr.text)
            if cid:
                self.db.update_contact(cid, **payload)
            else:
                self.db.add_contact(**payload)
            self.close_dialog()
            self.build_contacts()
            self.toast("Contato salvo!")

        buttons = [MDRaisedButton(text="Salvar", on_release=save),
                   MDFlatButton(text="Fechar", on_release=self.close_dialog)]
        if cid:
            buttons.insert(0, MDFlatButton(
                text="Excluir",
                on_release=lambda x: self.try_delete_contact(cid)))
        self.dialog = MDDialog(title="Contato", type="custom",
                               content_cls=content, buttons=buttons)
        self.dialog.open()

    def try_delete_contact(self, cid):
        ok = self.db.delete_contact(cid)
        self.close_dialog()
        if ok:
            self.toast("Contato excluido.")
        else:
            self.db.archive_contact(cid, True)
            self.toast("Tem vendas: contato arquivado (nao excluido).")
        self.build_contacts()

    # ---------------- Configuracoes ----------------
    def load_company_form(self, *_):
        c = self.db.get_company() or {}
        ids = self.root_widget.ids
        ids.co_name.text = c.get("name") or ""
        ids.co_document.text = c.get("document") or ""
        ids.co_phone.text = c.get("phone") or ""
        ids.co_email.text = c.get("email") or ""
        ids.co_address.text = c.get("address") or ""
        ids.co_currency.text = c.get("currency") or "R$"
        ids.co_footer.text = c.get("receipt_footer") or ""

    def save_company(self):
        ids = self.root_widget.ids
        self.db.save_company(
            name=ids.co_name.text, document=ids.co_document.text,
            phone=ids.co_phone.text, email=ids.co_email.text,
            address=ids.co_address.text, currency=ids.co_currency.text or "R$",
            receipt_footer=ids.co_footer.text, logo_path=None,
        )
        self.toast("Configuracoes salvas!")


if __name__ == "__main__":
    FinGestorApp().run()
