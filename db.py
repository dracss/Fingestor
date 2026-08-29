"""
FinGestor - Camada de dados e regras de negocio.

Banco local SQLite (offline-first). Dinheiro sempre em CENTAVOS (int) para
evitar erros de ponto flutuante. Datas em ISO 'YYYY-MM-DD' (texto).

Este modulo NAO depende de Kivy: pode ser testado no desktop com `python -c`.
"""
import os
import sqlite3
from datetime import date, datetime
from calendar import monthrange

# ---------------------------------------------------------------------------
# Utilidades de dinheiro e data
# ---------------------------------------------------------------------------

def cents_from_str(s):
    """Converte '1.234,56' ou '1234.56' ou '1234,56' em centavos (int)."""
    if s is None:
        return 0
    s = str(s).strip()
    if not s:
        return 0
    s = s.replace("R$", "").replace(" ", "")
    # Se tem virgula, assume virgula = separador decimal (padrao BR)
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return int(round(float(s) * 100))
    except ValueError:
        return 0


def fmt_money(cents, symbol="R$"):
    """Formata centavos como 'R$ 1.234,56'."""
    cents = int(cents or 0)
    neg = cents < 0
    cents = abs(cents)
    reais, cent = divmod(cents, 100)
    s = f"{reais:,}".replace(",", ".")
    out = f"{symbol} {s},{cent:02d}"
    return f"-{out}" if neg else out


def add_months(iso_date, months):
    """Soma meses a uma data ISO, tratando fim de mes (31 -> ultimo dia)."""
    d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    last = monthrange(y, m)[1]
    return date(y, m, min(d.day, last)).isoformat()


def today_iso():
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS company (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT, document TEXT, phone TEXT, email TEXT, address TEXT,
    logo_path TEXT, currency TEXT DEFAULT 'R$', receipt_footer TEXT
);
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'CLIENT',   -- CLIENT | SUPPLIER | BOTH
    phone TEXT, email TEXT, document TEXT, address TEXT, notes TEXT,
    archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER,
    description TEXT,
    gross_cents INTEGER NOT NULL DEFAULT 0,
    discount_cents INTEGER NOT NULL DEFAULT 0,
    discount_type TEXT NOT NULL DEFAULT 'FIXED',   -- FIXED | PERCENT
    net_cents INTEGER NOT NULL DEFAULT 0,
    payment_type TEXT NOT NULL DEFAULT 'CASH',     -- CASH | INSTALLMENT
    sale_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS installments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    number INTEGER NOT NULL,
    due_date TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    paid_cents INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    installment_id INTEGER,
    amount_cents INTEGER NOT NULL,
    payment_date TEXT NOT NULL,
    method TEXT DEFAULT 'CASH',
    FOREIGN KEY (installment_id) REFERENCES installments(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS payables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER,
    description TEXT,
    category TEXT,
    amount_cents INTEGER NOT NULL DEFAULT 0,
    paid_cents INTEGER NOT NULL DEFAULT 0,
    due_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_inst_sale ON installments(sale_id);
CREATE INDEX IF NOT EXISTS idx_inst_due  ON installments(due_date);
CREATE INDEX IF NOT EXISTS idx_sale_contact ON sales(contact_id);
CREATE INDEX IF NOT EXISTS idx_pay_due ON payables(due_date);
"""


class Database:
    def __init__(self, path):
        self.path = path
        new = not os.path.exists(path)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        if new or self.get_company() is None:
            self._ensure_company_row()

    # ----- Empresa -----
    def _ensure_company_row(self):
        cur = self.conn.execute("SELECT 1 FROM company WHERE id=1")
        if cur.fetchone() is None:
            self.conn.execute(
                "INSERT INTO company (id, name, currency) VALUES (1, ?, 'R$')",
                ("Minha Empresa",),
            )
            self.conn.commit()

    def get_company(self):
        cur = self.conn.execute("SELECT * FROM company WHERE id=1")
        r = cur.fetchone()
        return dict(r) if r else None

    def save_company(self, **f):
        self._ensure_company_row()
        cols = ["name", "document", "phone", "email", "address",
                "logo_path", "currency", "receipt_footer"]
        sets = ", ".join(f"{c}=?" for c in cols)
        vals = [f.get(c) for c in cols] + [1]
        self.conn.execute(f"UPDATE company SET {sets} WHERE id=?", vals)
        self.conn.commit()

    # ----- Contatos -----
    def add_contact(self, name, ctype="CLIENT", phone="", email="",
                    document="", address="", notes=""):
        cur = self.conn.execute(
            """INSERT INTO contacts (name,type,phone,email,document,address,notes,created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (name, ctype, phone, email, document, address, notes, today_iso()),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_contact(self, cid, **f):
        cols = ["name", "type", "phone", "email", "document", "address", "notes"]
        sets = ", ".join(f"{c}=?" for c in cols if c in f)
        vals = [f[c] for c in cols if c in f] + [cid]
        if sets:
            self.conn.execute(f"UPDATE contacts SET {sets} WHERE id=?", vals)
            self.conn.commit()

    def archive_contact(self, cid, archived=True):
        self.conn.execute("UPDATE contacts SET archived=? WHERE id=?",
                          (1 if archived else 0, cid))
        self.conn.commit()

    def delete_contact(self, cid):
        """Exclui somente se nao houver vendas (integridade). Retorna True/False."""
        n = self.conn.execute("SELECT COUNT(*) FROM sales WHERE contact_id=?",
                              (cid,)).fetchone()[0]
        if n > 0:
            return False
        self.conn.execute("DELETE FROM contacts WHERE id=?", (cid,))
        self.conn.commit()
        return True

    def list_contacts(self, include_archived=False, ctype=None, search=""):
        q = "SELECT * FROM contacts WHERE 1=1"
        args = []
        if not include_archived:
            q += " AND archived=0"
        if ctype and ctype != "ALL":
            q += " AND (type=? OR type='BOTH')"
            args.append(ctype)
        if search:
            q += " AND name LIKE ?"
            args.append(f"%{search}%")
        q += " ORDER BY name COLLATE NOCASE"
        return [dict(r) for r in self.conn.execute(q, args).fetchall()]

    def get_contact(self, cid):
        r = self.conn.execute("SELECT * FROM contacts WHERE id=?", (cid,)).fetchone()
        return dict(r) if r else None

    # ----- Regras de venda -----
    @staticmethod
    def compute_net(gross_cents, discount_value_cents, discount_type):
        """Aplica desconto. discount_value_cents: se PERCENT, e o percentual*100
        (ex.: 10% -> 1000). Retorna (net_cents, discount_cents)."""
        gross = int(gross_cents)
        if discount_type == "PERCENT":
            pct = discount_value_cents  # em centesimos de %
            disc = int(round(gross * pct / 10000.0))
        else:
            disc = int(discount_value_cents)
        disc = max(0, min(disc, gross))
        return gross - disc, disc

    @staticmethod
    def build_installments(net_cents, n, base_date):
        """Gera N parcelas mensais. O 'resto' de centavos vai na 1a parcela."""
        n = max(1, int(n))
        base = net_cents // n
        rest = net_cents - base * n
        out = []
        for i in range(n):
            amount = base + (rest if i == 0 else 0)
            out.append({
                "number": i + 1,
                "due_date": base_date if i == 0 else add_months(base_date, i),
                "amount_cents": amount,
            })
        return out

    def create_sale(self, contact_id, gross_cents, discount_value_cents,
                    discount_type, payment_type, n_installments,
                    sale_date=None, description=""):
        """Cria venda + parcelas numa unica transacao. Retorna sale_id."""
        sale_date = sale_date or today_iso()
        net, disc = self.compute_net(gross_cents, discount_value_cents, discount_type)
        n = 1 if payment_type == "CASH" else max(1, int(n_installments))
        try:
            cur = self.conn.execute(
                """INSERT INTO sales
                   (contact_id,description,gross_cents,discount_cents,discount_type,
                    net_cents,payment_type,sale_date,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (contact_id, description, gross_cents, disc, discount_type,
                 net, payment_type, sale_date, datetime.now().isoformat(timespec="seconds")),
            )
            sale_id = cur.lastrowid
            for ins in self.build_installments(net, n, sale_date):
                self.conn.execute(
                    """INSERT INTO installments (sale_id,number,due_date,amount_cents,paid_cents)
                       VALUES (?,?,?,?,0)""",
                    (sale_id, ins["number"], ins["due_date"], ins["amount_cents"]),
                )
            self.conn.commit()
            return sale_id
        except Exception:
            self.conn.rollback()
            raise

    def delete_sale(self, sale_id):
        self.conn.execute("DELETE FROM sales WHERE id=?", (sale_id,))
        self.conn.commit()

    def list_installments(self, sale_id):
        rows = self.conn.execute(
            "SELECT * FROM installments WHERE sale_id=? ORDER BY number", (sale_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def pay_installment(self, installment_id, amount_cents, method="CASH", pdate=None):
        """Registra baixa (parcial ou total) como lancamento imutavel."""
        pdate = pdate or today_iso()
        self.conn.execute(
            """INSERT INTO payments (installment_id,amount_cents,payment_date,method)
               VALUES (?,?,?,?)""",
            (installment_id, amount_cents, pdate, method),
        )
        self.conn.execute(
            "UPDATE installments SET paid_cents = paid_cents + ? WHERE id=?",
            (amount_cents, installment_id),
        )
        self.conn.commit()

    # ----- Status derivado (calculado na leitura) -----
    @staticmethod
    def installment_status(inst, ref=None):
        ref = ref or today_iso()
        paid = inst["paid_cents"]
        amount = inst["amount_cents"]
        if paid >= amount and amount > 0:
            return "PAID"
        if inst["due_date"] < ref and paid < amount:
            return "OVERDUE"
        if 0 < paid < amount:
            return "PARTIAL"
        return "PENDING"

    def sale_status(self, sale_id, ref=None):
        insts = self.list_installments(sale_id)
        if not insts:
            return "PENDING"
        statuses = [self.installment_status(i, ref) for i in insts]
        if all(s == "PAID" for s in statuses):
            return "PAID"
        if any(s == "OVERDUE" for s in statuses):
            return "OVERDUE"
        if any(s in ("PARTIAL", "PAID") for s in statuses):
            return "PARTIAL"
        return "PENDING"

    def list_sales(self, contact_id=None, status=None, search=""):
        q = "SELECT * FROM sales WHERE 1=1"
        args = []
        if contact_id:
            q += " AND contact_id=?"
            args.append(contact_id)
        if search:
            q += " AND description LIKE ?"
            args.append(f"%{search}%")
        q += " ORDER BY sale_date DESC, id DESC"
        rows = [dict(r) for r in self.conn.execute(q, args).fetchall()]
        for r in rows:
            r["status"] = self.sale_status(r["id"])
            c = self.get_contact(r["contact_id"]) if r["contact_id"] else None
            r["contact_name"] = c["name"] if c else "Sem cliente"
            total_paid = self.conn.execute(
                "SELECT COALESCE(SUM(paid_cents),0) FROM installments WHERE sale_id=?",
                (r["id"],)).fetchone()[0]
            r["paid_cents"] = total_paid
            r["open_cents"] = r["net_cents"] - total_paid
        if status and status != "ALL":
            rows = [r for r in rows if r["status"] == status]
        return rows

    def get_sale(self, sale_id):
        r = self.conn.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["status"] = self.sale_status(sale_id)
        c = self.get_contact(d["contact_id"]) if d["contact_id"] else None
        d["contact"] = c
        d["installments"] = self.list_installments(sale_id)
        return d

    # ----- Metricas / dashboard -----
    def total_receivable(self):
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount_cents - paid_cents),0) FROM installments "
            "WHERE amount_cents > paid_cents").fetchone()
        return row[0]

    def total_overdue(self, ref=None):
        ref = ref or today_iso()
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount_cents - paid_cents),0) FROM installments "
            "WHERE amount_cents > paid_cents AND due_date < ?", (ref,)).fetchone()
        return row[0]

    def received_this_month(self):
        ym = today_iso()[:7]
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount_cents),0) FROM payments "
            "WHERE substr(payment_date,1,7)=?", (ym,)).fetchone()
        return row[0]

    def upcoming(self, days=7, ref=None):
        ref = ref or today_iso()
        limit = add_months(ref, 0)  # placeholder
        from datetime import timedelta
        end = (date.fromisoformat(ref) + timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            """SELECT i.*, s.contact_id FROM installments i
               JOIN sales s ON s.id=i.sale_id
               WHERE i.amount_cents > i.paid_cents AND i.due_date <= ?
               ORDER BY i.due_date ASC LIMIT 30""", (end,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            c = self.get_contact(d["contact_id"]) if d["contact_id"] else None
            d["contact_name"] = c["name"] if c else "Sem cliente"
            d["status"] = self.installment_status(d, ref)
            out.append(d)
        return out

    def contact_totals(self, cid):
        """Total comprado e saldo devedor de um contato."""
        bought = self.conn.execute(
            "SELECT COALESCE(SUM(net_cents),0) FROM sales WHERE contact_id=?",
            (cid,)).fetchone()[0]
        owed = self.conn.execute(
            """SELECT COALESCE(SUM(i.amount_cents - i.paid_cents),0)
               FROM installments i JOIN sales s ON s.id=i.sale_id
               WHERE s.contact_id=? AND i.amount_cents > i.paid_cents""",
            (cid,)).fetchone()[0]
        return {"bought_cents": bought, "owed_cents": owed}

    # ----- Contas a pagar -----
    def add_payable(self, description, amount_cents, due_date=None,
                    contact_id=None, category=""):
        due_date = due_date or today_iso()
        cur = self.conn.execute(
            """INSERT INTO payables (contact_id,description,category,amount_cents,
                                     paid_cents,due_date,created_at)
               VALUES (?,?,?,?,0,?,?)""",
            (contact_id, description, category, amount_cents, due_date, today_iso()),
        )
        self.conn.commit()
        return cur.lastrowid

    def pay_payable(self, payable_id, amount_cents):
        self.conn.execute(
            "UPDATE payables SET paid_cents = paid_cents + ? WHERE id=?",
            (amount_cents, payable_id))
        self.conn.commit()

    def delete_payable(self, payable_id):
        self.conn.execute("DELETE FROM payables WHERE id=?", (payable_id,))
        self.conn.commit()

    @staticmethod
    def payable_status(p, ref=None):
        ref = ref or today_iso()
        if p["paid_cents"] >= p["amount_cents"] and p["amount_cents"] > 0:
            return "PAID"
        if p["due_date"] < ref and p["paid_cents"] < p["amount_cents"]:
            return "OVERDUE"
        if 0 < p["paid_cents"] < p["amount_cents"]:
            return "PARTIAL"
        return "PENDING"

    def list_payables(self, only_open=False):
        rows = [dict(r) for r in self.conn.execute(
            "SELECT * FROM payables ORDER BY due_date ASC, id DESC").fetchall()]
        for r in rows:
            r["status"] = self.payable_status(r)
            r["open_cents"] = r["amount_cents"] - r["paid_cents"]
            c = self.get_contact(r["contact_id"]) if r["contact_id"] else None
            r["contact_name"] = c["name"] if c else ""
        if only_open:
            rows = [r for r in rows if r["open_cents"] > 0]
        return rows

    def get_payable(self, pid):
        r = self.conn.execute("SELECT * FROM payables WHERE id=?", (pid,)).fetchone()
        return dict(r) if r else None

    def total_payable(self):
        return self.conn.execute(
            "SELECT COALESCE(SUM(amount_cents - paid_cents),0) FROM payables "
            "WHERE amount_cents > paid_cents").fetchone()[0]

    def total_payable_overdue(self, ref=None):
        ref = ref or today_iso()
        return self.conn.execute(
            "SELECT COALESCE(SUM(amount_cents - paid_cents),0) FROM payables "
            "WHERE amount_cents > paid_cents AND due_date < ?", (ref,)).fetchone()[0]

    # ----- Relatorios -----
    def sales_by_client(self):
        """Retorna [{name, count, net_cents, paid_cents, open_cents}] por cliente."""
        rows = self.conn.execute("""
            SELECT c.id AS cid, c.name AS name,
                   COUNT(s.id) AS n,
                   COALESCE(SUM(s.net_cents),0) AS net
            FROM contacts c JOIN sales s ON s.contact_id = c.id
            GROUP BY c.id ORDER BY net DESC
        """).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            tot = self.contact_totals(d["cid"])
            paid = self.conn.execute("""
                SELECT COALESCE(SUM(i.paid_cents),0)
                FROM installments i JOIN sales s ON s.id=i.sale_id
                WHERE s.contact_id=?""", (d["cid"],)).fetchone()[0]
            out.append({
                "name": d["name"], "count": d["n"],
                "net_cents": d["net"], "paid_cents": paid,
                "open_cents": tot["owed_cents"],
            })
        return out

    def sales_summary(self, start=None, end=None):
        """Totais de vendas (opcionalmente por periodo)."""
        q = "SELECT COUNT(*) n, COALESCE(SUM(net_cents),0) net FROM sales WHERE 1=1"
        args = []
        if start:
            q += " AND sale_date >= ?"; args.append(start)
        if end:
            q += " AND sale_date <= ?"; args.append(end)
        r = self.conn.execute(q, args).fetchone()
        n, net = r[0], r[1]
        return {"count": n, "net_cents": net,
                "avg_cents": (net // n) if n else 0}

    def payable_vs_receivable(self):
        recv = self.total_receivable()
        pay = self.total_payable()
        return {"receivable_cents": recv, "payable_cents": pay,
                "balance_cents": recv - pay}

    def close(self):
        self.conn.close()


STATUS_LABEL = {
    "PENDING": "Pendente", "PAID": "Pago", "OVERDUE": "Atrasado",
    "PARTIAL": "Parcial", "CASH": "A vista", "INSTALLMENT": "Parcelado",
}
STATUS_COLOR = {
    "PENDING": (0.95, 0.61, 0.07, 1),   # ambar
    "PAID": (0.18, 0.65, 0.32, 1),      # verde
    "OVERDUE": (0.83, 0.18, 0.18, 1),   # vermelho
    "PARTIAL": (0.20, 0.47, 0.87, 1),   # azul
}
