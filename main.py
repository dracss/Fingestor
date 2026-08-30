"""
FinGestor - App de contas a pagar e a receber (Fase 2).
UI em KivyMD; dados em SQLite (db.py); cupom e relatorios em PNG/PDF (receipt.py).

Testavel no desktop:  python main.py
Empacotavel em APK:   via GitHub Actions (.github/workflows) ou `buildozer android debug`
"""
import os
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.window import Window
from kivy.properties import StringProperty

from kivymd.app import MDApp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.list import (
    ThreeLineListItem, TwoLineListItem, OneLineListItem, MDList,
)
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.snackbar import MDSnackbar
from kivy.uix.scrollview import ScrollView

from db import Database, fmt_money, cents_from_str, STATUS_LABEL, today_iso
import receipt

# Tamanho de janela SOMENTE no desktop; no celular a tela e usada por completo.
from kivy.utils import platform as _platform
if _platform not in ("android", "ios"):
    Window.size = (400, 720)


class StatCard(MDCard):
    value = StringProperty("")
    label = StringProperty("")


KV = '''
#:import dp kivy.metrics.dp

<StatCard>:
    orientation: "vertical"
    padding: dp(14)
    radius: [16,]
    md_bg_color: app.theme_cls.primary_light
    size_hint_y: None
    height: dp(92)
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
                right_action_items: [["cog", lambda x: app.open_settings()], ["refresh", lambda x: app.refresh_all()]]
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
                            height: dp(52)
                            padding: dp(8), 0
                            spacing: dp(6)
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
                    name: "tab_payables"
                    text: "Pagar"
                    icon: "arrow-up-bold-box"
                    ScrollView:
                        MDList:
                            id: payables_list

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
                    name: "tab_reports"
                    text: "Relat."
                    icon: "chart-box"
                    ScrollView:
                        MDBoxLayout:
                            id: reports_box
                            orientation: "vertical"
                            padding: dp(12)
                            spacing: dp(8)
                            adaptive_height: True

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
                        on_release: app.open_contact_picker(app.pick_sale_client)
                    MDTextField:
                        id: ns_desc
                        hint_text: "Descricao (opcional)"
                    MDTextField:
                        id: ns_gross
                        hint_text: "Valor bruto (ex: 150,00)"
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

    Screen:
        name: "settings"
        MDBoxLayout:
            orientation: "vertical"
            MDTopAppBar:
                title: "Configuracoes"
                left_action_items: [["arrow-left", lambda x: app.go_main("tab_home")]]
            ScrollView:
                MDBoxLayout:
                    orientation: "vertical"
                    padding: dp(16)
                    spacing: dp(8)
                    adaptive_height: True
                    MDLabel:
                        text: "Dados da empresa / vendedor"
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
                    MDLabel:
                        text: "Backup e restauracao"
                        font_style: "H6"
                        adaptive_height: True
                        padding: 0, dp(8)
                    MDLabel:
                        text: "Faca um backup e envie para o seu Google Drive, e-mail ou WhatsApp. Para restaurar, baixe o arquivo e escolha 'Restaurar backup'."
                        theme_text_color: "Secondary"
                        adaptive_height: True
                    MDBoxLayout:
                        adaptive_height: True
                        spacing: dp(8)
                        padding: 0, dp(6)
                        MDRaisedButton:
                            text: "Fazer backup"
                            on_release: app.do_backup()
                        MDFlatButton:
                            text: "Restaurar backup"
                            on_release: app.do_restore()

    Screen:
        name: "receivables"
        MDBoxLayout:
            orientation: "vertical"
            MDTopAppBar:
                title: "Contas a receber"
                left_action_items: [["arrow-left", lambda x: app.go_main("tab_home")]]
            ScrollView:
                MDList:
                    id: receivables_list

    Screen:
        name: "contact_form"
        MDBoxLayout:
            orientation: "vertical"
            MDTopAppBar:
                id: cf_bar
                title: "Contato"
                left_action_items: [["arrow-left", lambda x: app.go_main("tab_contacts")]]
            ScrollView:
                MDBoxLayout:
                    orientation: "vertical"
                    padding: dp(16)
                    spacing: dp(12)
                    adaptive_height: True
                    MDTextField:
                        id: cf_name
                        hint_text: "Nome *"
                    MDTextField:
                        id: cf_phone
                        hint_text: "Telefone"
                    MDTextField:
                        id: cf_email
                        hint_text: "E-mail"
                    MDTextField:
                        id: cf_doc
                        hint_text: "CPF / CNPJ"
                    MDTextField:
                        id: cf_address
                        hint_text: "Endereco"
                    MDBoxLayout:
                        adaptive_height: True
                        spacing: dp(8)
                        padding: 0, dp(8)
                        MDRaisedButton:
                            text: "Salvar"
                            on_release: app.save_contact_form()
                        MDFlatButton:
                            id: cf_delete
                            text: "Excluir"
                            on_release: app.delete_contact_form()

    Screen:
        name: "payable_form"
        MDBoxLayout:
            orientation: "vertical"
            MDTopAppBar:
                title: "Nova conta a pagar"
                left_action_items: [["arrow-left", lambda x: app.go_main("tab_payables")]]
            ScrollView:
                MDBoxLayout:
                    orientation: "vertical"
                    padding: dp(16)
                    spacing: dp(12)
                    adaptive_height: True
                    MDRaisedButton:
                        id: pf_supplier
                        text: "Fornecedor (opcional)"
                        on_release: app.open_contact_picker(app.pick_payable_supplier)
                    MDTextField:
                        id: pf_desc
                        hint_text: "Descricao *"
                    MDTextField:
                        id: pf_amount
                        hint_text: "Valor (ex: 200,00)"
                    MDTextField:
                        id: pf_due
                        hint_text: "Vencimento (AAAA-MM-DD)"
                    MDTextField:
                        id: pf_cat
                        hint_text: "Categoria (opcional)"
                    MDRaisedButton:
                        text: "Salvar"
                        pos_hint: {"center_x": 0.5}
                        on_release: app.save_payable_form()
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
        self.sale_client_id = None
        self.payable_supplier_id = None
        self.editing_contact_id = None
        self.discount_type = "FIXED"
        self.sales_filter = "ALL"
        self.current_sale_id = None
        self.root_widget = Builder.load_string(KV)
        return self.root_widget

    def on_start(self):
        self.build_dashboard()
        self.build_sales()
        self.build_payables()
        self.build_contacts()
        self.build_reports()
        self.load_company_form()

    # ---------------- utilitarios de UI ----------------
    TAB_TITLES = {
        "tab_home": "Inicio", "tab_sales": "Vendas", "tab_payables": "A Pagar",
        "tab_contacts": "Contatos", "tab_reports": "Relatorios",
    }

    def ids(self):
        return self.root_widget.ids

    def set_title(self, t):
        self.root_widget.ids.top_bar.title = t

    def toast(self, msg):
        try:
            MDSnackbar(
                MDLabel(text=str(msg)),
                y=dp(24), pos_hint={"center_x": 0.5}, size_hint_x=0.9,
            ).open()
        except Exception:
            print("TOAST:", msg)

    def show_message(self, title, text):
        self.close_dialog()
        self.dialog = MDDialog(title=title, text=str(text),
                               buttons=[MDFlatButton(text="Fechar",
                                        on_release=self.close_dialog)])
        self.dialog.open()

    def on_tab_switch(self, *args):
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
        {
            "tab_home": self.build_dashboard,
            "tab_sales": self.build_sales,
            "tab_payables": self.build_payables,
            "tab_contacts": self.build_contacts,
            "tab_reports": self.build_reports,
        }.get(name, lambda: None)()

    def go_main(self, tab=None):
        self.root_widget.current = "main"
        if tab:
            self.root_widget.ids.bottom_nav.switch_tab(tab)
        self.refresh_all()

    def refresh_all(self, *_):
        self.build_dashboard()
        self.build_sales()
        self.build_payables()
        self.build_contacts()
        self.build_reports()

    def close_dialog(self, *_):
        if self.dialog:
            self.dialog.dismiss()
            self.dialog = None

    def open_settings(self, *_):
        self.load_company_form()
        self.root_widget.current = "settings"

    # ---------------- Dashboard ----------------
    def build_dashboard(self, *_):
        box = self.root_widget.ids.dash_box
        box.clear_widgets()
        recv = self.db.total_receivable()
        overdue = self.db.total_overdue()
        month = self.db.received_this_month()
        pay = self.db.total_payable()
        balance = recv - pay

        def card(value, label, bg):
            c = StatCard()
            c.value = value
            c.label = label
            c.md_bg_color = bg
            return c

        box.add_widget(card(fmt_money(recv), "A receber (em aberto)", (0.90, 0.97, 0.95, 1)))
        box.add_widget(card(fmt_money(pay), "A pagar (em aberto)", (0.99, 0.95, 0.90, 1)))
        box.add_widget(card(fmt_money(balance), "Saldo projetado", (0.93, 0.96, 0.99, 1)))
        box.add_widget(card(fmt_money(overdue), "Vencido a receber", (0.99, 0.92, 0.92, 1)))
        box.add_widget(card(fmt_money(month), "Recebido no mes", (0.94, 0.94, 0.97, 1)))

        actions = MDBoxLayout(adaptive_height=True, spacing=dp(8), padding=(0, dp(6)))
        actions.add_widget(MDRaisedButton(text="Contas a receber",
                           on_release=lambda x: self.open_receivables()))
        actions.add_widget(MDFlatButton(text="Contas a pagar",
                           on_release=lambda x: self.go_main("tab_payables")))
        box.add_widget(actions)

        box.add_widget(MDLabel(text="Proximos vencimentos (7 dias)",
                               font_style="H6", adaptive_height=True))
        up = self.db.upcoming(days=7)
        if not up:
            box.add_widget(MDLabel(text="Nada a vencer nos proximos 7 dias.",
                                   theme_text_color="Secondary", adaptive_height=True))
        for i in up:
            open_c = i["amount_cents"] - i["paid_cents"]
            box.add_widget(TwoLineListItem(
                text=f"{i['contact_name']}  -  {fmt_money(open_c)}",
                secondary_text=f"Venc. {i['due_date']}  [{STATUS_LABEL.get(i['status'],'')}]",
                on_release=lambda x, sid=i["sale_id"]: self.open_sale(sid),
            ))

    # ---------------- Vendas ----------------
    def set_sales_filter(self, f):
        self.sales_filter = f
        self.build_sales()

    def build_sales(self, *_):
        lst = self.root_widget.ids.sales_list
        lst.clear_widgets()
        lst.add_widget(OneLineListItem(text="+  Nova venda",
                       on_release=lambda x: self.start_new_sale()))
        rows = self.db.list_sales()
        if self.sales_filter == "OPEN":
            rows = [r for r in rows if r["open_cents"] > 0]
        elif self.sales_filter == "OVERDUE":
            rows = [r for r in rows if r["status"] == "OVERDUE"]
        if not rows:
            lst.add_widget(OneLineListItem(text="Nenhuma venda ainda."))
        for r in rows:
            lst.add_widget(ThreeLineListItem(
                text=f"{r['contact_name']}  -  {fmt_money(r['net_cents'])}",
                secondary_text=f"{r['sale_date']}  |  {STATUS_LABEL.get(r['status'],'')}",
                tertiary_text=f"Em aberto: {fmt_money(r['open_cents'])}",
                on_release=lambda x, sid=r["id"]: self.open_sale(sid),
            ))

    def start_new_sale(self, *_):
        ids = self.root_widget.ids
        self.sale_client_id = None
        self.discount_type = "FIXED"
        ids.ns_client_btn.text = "Selecionar cliente"
        ids.ns_desc.text = ""
        ids.ns_gross.text = ""
        ids.ns_discount.text = "0"
        ids.ns_disc_type.text = "R$"
        ids.ns_installment.active = False
        ids.ns_nparc.text = "1"
        ids.ns_nparc.disabled = True
        self.root_widget.current = "new_sale"

    def on_installment_toggle(self, active):
        ids = self.root_widget.ids
        ids.ns_nparc.disabled = not active
        if not active:
            ids.ns_nparc.text = "1"

    def toggle_discount_type(self):
        ids = self.root_widget.ids
        self.discount_type = "PERCENT" if self.discount_type == "FIXED" else "FIXED"
        ids.ns_disc_type.text = "%" if self.discount_type == "PERCENT" else "R$"

    def pick_sale_client(self, cid, name):
        self.sale_client_id = cid
        self.root_widget.ids.ns_client_btn.text = name
        self.close_dialog()

    def save_sale(self):
        ids = self.root_widget.ids
        gross = cents_from_str(ids.ns_gross.text)
        if gross <= 0:
            self.toast("Informe um valor bruto valido.")
            return
        disc_val = cents_from_str(ids.ns_discount.text)
        installment = ids.ns_installment.active
        try:
            n = int(ids.ns_nparc.text or "1")
        except ValueError:
            n = 1
        sale_id = self.db.create_sale(
            contact_id=self.sale_client_id, gross_cents=gross,
            discount_value_cents=disc_val, discount_type=self.discount_type,
            payment_type="INSTALLMENT" if installment else "CASH",
            n_installments=n, description=ids.ns_desc.text,
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
            item = TwoLineListItem(
                text=f"{i['number']}/{len(sale['installments'])}  -  {fmt_money(i['amount_cents'])}",
                secondary_text=f"Venc. {i['due_date']}  [{STATUS_LABEL.get(st,'')}]  aberto {fmt_money(open_c)}")
            if open_c > 0:
                item.on_release = lambda x, iid=i["id"], oc=open_c: self.open_pay_dialog(iid, oc)
            box.add_widget(item)

        btns = MDBoxLayout(adaptive_height=True, spacing=dp(8), padding=(0, dp(12)))
        btns.add_widget(MDRaisedButton(text="Cupom PDF",
                        on_release=lambda x: self.make_receipt("pdf")))
        btns.add_widget(MDRaisedButton(text="Cupom PNG",
                        on_release=lambda x: self.make_receipt("png")))
        box.add_widget(btns)

    def open_pay_dialog(self, installment_id, open_cents):
        field = MDTextField(hint_text="Valor da baixa",
                            text=f"{open_cents/100:.2f}".replace(".", ","))
        content = MDBoxLayout(orientation="vertical", adaptive_height=True,
                              size_hint_y=None, height=dp(90), padding=dp(8))
        content.add_widget(field)
        self.dialog = MDDialog(
            title="Dar baixa", type="custom", content_cls=content,
            buttons=[
                MDFlatButton(text="Total",
                             on_release=lambda x: self.do_pay(installment_id, open_cents)),
                MDRaisedButton(text="Confirmar",
                               on_release=lambda x: self.do_pay(installment_id,
                                                                cents_from_str(field.text))),
                MDFlatButton(text="Cancelar", on_release=self.close_dialog),
            ])
        self.dialog.open()

    def do_pay(self, installment_id, amount_cents):
        if amount_cents <= 0:
            self.toast("Valor invalido.")
            return
        self.db.pay_installment(installment_id, amount_cents)
        self.close_dialog()
        self.toast("Baixa registrada!")
        self.build_dashboard()
        if self.root_widget.current == "sale_detail":
            self.render_sale_detail()
        elif self.root_widget.current == "receivables":
            self.build_receivables()

    # ---------------- Contas a receber (baixa rapida) ----------------
    def open_receivables(self, *_):
        self.build_receivables()
        self.root_widget.current = "receivables"

    def build_receivables(self, *_):
        lst = self.root_widget.ids.receivables_list
        lst.clear_widgets()
        rows = self.db.list_open_installments()
        if not rows:
            lst.add_widget(OneLineListItem(text="Nada a receber em aberto."))
        for i in rows:
            lst.add_widget(ThreeLineListItem(
                text=f"{i['contact_name']}  -  {fmt_money(i['open_cents'])}",
                secondary_text=f"Venc. {i['due_date']}  [{STATUS_LABEL.get(i['status'],'')}]",
                tertiary_text=f"Venda #{i['sale_id']:05d}  parcela {i['number']}",
                on_release=lambda x, iid=i["id"], oc=i["open_cents"]: self.open_pay_dialog(iid, oc),
            ))

    # ---------------- Cupom (com feedback visivel) ----------------
    def make_receipt(self, fmt):
        try:
            sale = self.db.get_sale(self.current_sale_id)
            company = self.db.get_company()
            out_dir = os.path.join(self.user_data_dir, "cupons")
            paths = receipt.save_receipt(sale, company, out_dir, fmt=fmt)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.show_message("Erro ao gerar cupom", f"{type(e).__name__}: {e}")
            return
        path = paths.get(fmt) or next(iter(paths.values()))
        mime = "application/pdf" if fmt == "pdf" else "image/png"
        self._show_doc_result("Cupom gerado", path, mime)

    def _show_doc_result(self, title, path, mime):
        self.close_dialog()
        self.dialog = MDDialog(
            title=title,
            text=f"Arquivo salvo em:\n{path}\n\nToque em Compartilhar para enviar "
                 f"pelo WhatsApp, e-mail, etc.",
            buttons=[
                MDRaisedButton(text="Compartilhar",
                               on_release=lambda x: self._do_share(path, mime)),
                MDFlatButton(text="Fechar", on_release=self.close_dialog),
            ])
        self.dialog.open()

    def _do_share(self, path, mime):
        ok, err = receipt.share_file(path, mime=mime)
        if not ok:
            self.show_message(
                "Nao foi possivel compartilhar",
                f"O arquivo esta salvo no aparelho em:\n{path}\n\n"
                f"Detalhe tecnico (para suporte):\n{err}")

    # ---------------- Contas a pagar ----------------
    def build_payables(self, *_):
        lst = self.root_widget.ids.payables_list
        lst.clear_widgets()
        lst.add_widget(OneLineListItem(text="+  Nova conta a pagar",
                       on_release=lambda x: self.open_payable_form()))
        rows = self.db.list_payables()
        if not rows:
            lst.add_widget(OneLineListItem(text="Nenhuma conta a pagar."))
        for p in rows:
            who = p["contact_name"] or (p["description"] or "Conta")
            lst.add_widget(ThreeLineListItem(
                text=f"{who}  -  {fmt_money(p['amount_cents'])}",
                secondary_text=f"Venc. {p['due_date']}  |  {STATUS_LABEL.get(p['status'],'')}",
                tertiary_text=f"Em aberto: {fmt_money(p['open_cents'])}  {('· '+p['description']) if p['contact_name'] and p['description'] else ''}",
                on_release=lambda x, pid=p["id"]: self.open_payable_detail(pid),
            ))

    def open_payable_form(self, *_):
        self.payable_supplier_id = None
        ids = self.root_widget.ids
        ids.pf_supplier.text = "Fornecedor (opcional)"
        ids.pf_desc.text = ""
        ids.pf_amount.text = ""
        ids.pf_due.text = today_iso()
        ids.pf_cat.text = ""
        self.root_widget.current = "payable_form"

    def pick_payable_supplier(self, cid, name):
        self.payable_supplier_id = cid
        self.root_widget.ids.pf_supplier.text = name or "Fornecedor (opcional)"
        self.close_dialog()

    def save_payable_form(self):
        ids = self.root_widget.ids
        amt = cents_from_str(ids.pf_amount.text)
        if not ids.pf_desc.text.strip() or amt <= 0:
            self.toast("Informe descricao e valor validos.")
            return
        self.db.add_payable(description=ids.pf_desc.text.strip(), amount_cents=amt,
                            due_date=ids.pf_due.text.strip() or today_iso(),
                            contact_id=self.payable_supplier_id,
                            category=ids.pf_cat.text.strip())
        self.toast("Conta a pagar registrada!")
        self.go_main("tab_payables")

    def open_payable_detail(self, pid):
        p = self.db.get_payable(pid)
        if not p:
            return
        open_c = p["amount_cents"] - p["paid_cents"]
        field = MDTextField(hint_text="Valor da baixa",
                            text=f"{max(open_c,0)/100:.2f}".replace(".", ","))
        content = MDBoxLayout(orientation="vertical", adaptive_height=True,
                              size_hint_y=None, height=dp(130), padding=dp(8), spacing=dp(6))
        content.add_widget(MDLabel(
            text=f"{p['description']}\nTotal {fmt_money(p['amount_cents'])} | "
                 f"aberto {fmt_money(open_c)}",
            adaptive_height=True))
        content.add_widget(field)
        buttons = [MDFlatButton(text="Excluir",
                                on_release=lambda x: self._del_payable(pid))]
        if open_c > 0:
            buttons += [
                MDFlatButton(text="Baixa total",
                             on_release=lambda x: self._pay_payable(pid, open_c)),
                MDRaisedButton(text="Confirmar",
                               on_release=lambda x: self._pay_payable(pid, cents_from_str(field.text))),
            ]
        buttons.append(MDFlatButton(text="Fechar", on_release=self.close_dialog))
        self.dialog = MDDialog(title="Conta a pagar", type="custom",
                               content_cls=content, buttons=buttons)
        self.dialog.open()

    def _pay_payable(self, pid, amount):
        if amount <= 0:
            self.toast("Valor invalido.")
            return
        self.db.pay_payable(pid, amount)
        self.close_dialog()
        self.build_payables()
        self.build_dashboard()
        self.toast("Baixa registrada!")

    def _del_payable(self, pid):
        self.db.delete_payable(pid)
        self.close_dialog()
        self.build_payables()
        self.build_dashboard()
        self.toast("Conta excluida.")

    # ---------------- Relatorios ----------------
    def build_reports(self, *_):
        box = self.root_widget.ids.reports_box
        box.clear_widgets()
        pv = self.db.payable_vs_receivable()
        summ = self.db.sales_summary()

        box.add_widget(MDLabel(text="Resumo financeiro", font_style="H6",
                               adaptive_height=True))
        for label, val in (
            ("A receber (em aberto)", pv["receivable_cents"]),
            ("A pagar (em aberto)", pv["payable_cents"]),
            ("Saldo projetado", pv["balance_cents"]),
        ):
            box.add_widget(TwoLineListItem(text=fmt_money(val), secondary_text=label))

        box.add_widget(MDLabel(
            text=f"Vendas: {summ['count']}  |  Total {fmt_money(summ['net_cents'])}  |  "
                 f"Ticket medio {fmt_money(summ['avg_cents'])}",
            theme_text_color="Secondary", adaptive_height=True))

        box.add_widget(MDLabel(text="Vendas por cliente", font_style="H6",
                               adaptive_height=True))
        rows = self.db.sales_by_client()
        if not rows:
            box.add_widget(MDLabel(text="Sem vendas ainda.",
                                   theme_text_color="Secondary", adaptive_height=True))
        for r in rows:
            box.add_widget(ThreeLineListItem(
                text=f"{r['name']}  -  {fmt_money(r['net_cents'])}",
                secondary_text=f"{r['count']} venda(s)  |  em aberto {fmt_money(r['open_cents'])}",
                tertiary_text=f"recebido {fmt_money(r['paid_cents'])}"))

        btns = MDBoxLayout(adaptive_height=True, spacing=dp(8), padding=(0, dp(10)))
        btns.add_widget(MDRaisedButton(text="Exportar PDF",
                        on_release=lambda x: self.export_report("pdf")))
        btns.add_widget(MDRaisedButton(text="Exportar PNG",
                        on_release=lambda x: self.export_report("png")))
        box.add_widget(btns)

    def export_report(self, fmt):
        try:
            company = self.db.get_company()
            pv = self.db.payable_vs_receivable()
            summ = self.db.sales_summary()
            sections = [
                ("Resumo financeiro", [
                    ("A receber (em aberto)", fmt_money(pv["receivable_cents"])),
                    ("A pagar (em aberto)", fmt_money(pv["payable_cents"])),
                    ("Saldo projetado", fmt_money(pv["balance_cents"])),
                    ("Vendas (qtd)", str(summ["count"])),
                    ("Total vendido", fmt_money(summ["net_cents"])),
                    ("Ticket medio", fmt_money(summ["avg_cents"])),
                ]),
                ("Vendas por cliente", [
                    (f"{r['name']} ({r['count']})",
                     f"{fmt_money(r['net_cents'])}  ab.{fmt_money(r['open_cents'])}")
                    for r in self.db.sales_by_client()
                ]),
            ]
            out_dir = os.path.join(self.user_data_dir, "relatorios")
            paths = receipt.save_report("Relatorio Financeiro", company, sections,
                                        out_dir, "relatorio",
                                        subtitle=f"Gerado em {today_iso()}", fmt=fmt)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.show_message("Erro ao gerar relatorio", f"{type(e).__name__}: {e}")
            return
        path = paths.get(fmt) or next(iter(paths.values()))
        mime = "application/pdf" if fmt == "pdf" else "image/png"
        self._show_doc_result("Relatorio gerado", path, mime)

    # ---------------- Contatos ----------------
    def build_contacts(self, *_):
        lst = self.root_widget.ids.contacts_list
        search = self.root_widget.ids.contact_search.text
        lst.clear_widgets()
        lst.add_widget(OneLineListItem(text="+  Novo contato",
                       on_release=lambda x: self.open_contact_form()))
        contacts = self.db.list_contacts(search=search)
        if not contacts:
            lst.add_widget(OneLineListItem(text="Nenhum contato."))
        for c in contacts:
            tot = self.db.contact_totals(c["id"])
            lst.add_widget(TwoLineListItem(
                text=c["name"],
                secondary_text=f"{c.get('phone') or ''}  |  Devedor: {fmt_money(tot['owed_cents'])}",
                on_release=lambda x, cid=c["id"]: self.open_contact_form(cid),
            ))

    def open_contact_form(self, cid=None):
        """Abre a TELA de contato (evita o problema de campo cortado no dialogo)."""
        self.editing_contact_id = cid
        data = self.db.get_contact(cid) if cid else {}
        ids = self.root_widget.ids
        ids.cf_bar.title = "Editar contato" if cid else "Novo contato"
        ids.cf_name.text = (data.get("name") or "") if data else ""
        ids.cf_phone.text = (data.get("phone") or "") if data else ""
        ids.cf_email.text = (data.get("email") or "") if data else ""
        ids.cf_doc.text = (data.get("document") or "") if data else ""
        ids.cf_address.text = (data.get("address") or "") if data else ""
        ids.cf_delete.disabled = cid is None
        ids.cf_delete.opacity = 1 if cid else 0
        self.root_widget.current = "contact_form"

    def save_contact_form(self):
        ids = self.root_widget.ids
        if not ids.cf_name.text.strip():
            self.toast("Nome obrigatorio.")
            return
        payload = dict(name=ids.cf_name.text.strip(), phone=ids.cf_phone.text,
                       email=ids.cf_email.text, document=ids.cf_doc.text,
                       address=ids.cf_address.text)
        if self.editing_contact_id:
            self.db.update_contact(self.editing_contact_id, **payload)
        else:
            self.db.add_contact(**payload)
        self.toast("Contato salvo!")
        self.go_main("tab_contacts")

    def delete_contact_form(self):
        cid = self.editing_contact_id
        if not cid:
            return
        if self.db.delete_contact(cid):
            self.toast("Contato excluido.")
        else:
            self.db.archive_contact(cid, True)
            self.toast("Tem vendas: contato arquivado.")
        self.go_main("tab_contacts")

    # Picker de contato reutilizavel (vendas e fornecedores)
    def open_contact_picker(self, on_pick):
        contacts = self.db.list_contacts()
        ml = MDList()
        ml.add_widget(OneLineListItem(text="(Nenhum)",
                      on_release=lambda x: on_pick(None, "")))
        for c in contacts:
            ml.add_widget(OneLineListItem(
                text=c["name"],
                on_release=lambda x, cid=c["id"], nm=c["name"]: on_pick(cid, nm)))
        sv = ScrollView()
        sv.add_widget(ml)
        content = MDBoxLayout(orientation="vertical", size_hint_y=None,
                              height=dp(min(400, 56 * (len(contacts) + 2))))
        content.add_widget(sv)
        self.dialog = MDDialog(title="Selecionar contato", type="custom",
                               content_cls=content,
                               buttons=[MDFlatButton(text="Novo contato",
                                        on_release=lambda x: (self.close_dialog(),
                                                              self.open_contact_form())),
                                        MDFlatButton(text="Fechar",
                                        on_release=self.close_dialog)])
        self.dialog.open()

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
            receipt_footer=ids.co_footer.text, logo_path=None)
        self.toast("Configuracoes salvas!")
        self.go_main("tab_home")

    # ---------------- Backup / restauracao ----------------
    def do_backup(self):
        import datetime
        try:
            out_dir = os.path.join(self.user_data_dir, "backups")
            os.makedirs(out_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(out_dir, f"fingestor_backup_{ts}.db")
            self.db.backup_to(dest)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.show_message("Erro no backup", f"{type(e).__name__}: {e}")
            return
        self._show_doc_result("Backup criado", dest, "application/octet-stream")

    def do_restore(self):
        # Abre o seletor de arquivos do Android (SAF) e restaura o backup.
        try:
            from jnius import autoclass
            from android import activity  # p4a
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType("*/*")
            self._restore_req = 4242
            activity.bind(on_activity_result=self._on_restore_result)
            PythonActivity.mActivity.startActivityForResult(intent, self._restore_req)
        except Exception as e:
            self.show_message(
                "Restaurar backup",
                "A selecao de arquivo so funciona no aparelho Android.\n\n"
                f"Detalhe: {type(e).__name__}: {e}")

    def _on_restore_result(self, request_code, result_code, intent):
        from kivy.clock import Clock
        try:
            from android import activity
            activity.unbind(on_activity_result=self._on_restore_result)
        except Exception:
            pass
        if intent is None or request_code != getattr(self, "_restore_req", None):
            return
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            act = PythonActivity.mActivity
            uri = intent.getData()
            if uri is None:
                return
            resolver = act.getContentResolver()
            istream = resolver.openInputStream(uri)
            tmp = os.path.join(self.user_data_dir, "_restore_tmp.db")
            with open(tmp, "wb") as f:
                buf = bytearray(8192)
                n = istream.read(buf)
                while n is not None and n != -1:
                    if n > 0:
                        f.write(bytes(buf[:n]))
                    n = istream.read(buf)
            istream.close()
            ok, err = self.db.restore_from(tmp)
            try:
                os.remove(tmp)
            except Exception:
                pass
            Clock.schedule_once(lambda dt: self._after_restore(ok, err), 0)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            Clock.schedule_once(lambda dt: self.show_message("Erro na restauracao", msg), 0)

    def _after_restore(self, ok, err):
        if ok:
            self.refresh_all()
            self.load_company_form()
            self.go_main("tab_home")
            self.toast("Backup restaurado!")
        else:
            self.show_message("Nao foi possivel restaurar", err or "Arquivo invalido.")


if __name__ == "__main__":
    FinGestorApp().run()
