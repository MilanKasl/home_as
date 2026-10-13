"""Application diagnostics for direct RX and operator-confirmed port mapping."""
import tkinter as tk
from tkinter import messagebox


NAMES = {'cov': 'ČOV', 'reg': 'regulátor', 'heating': 'ohřev', 'pump': 'čerpadlo', 'outdoor': 'venkovní'}


def diagnostic_text(link):
    snapshot = link.debug_snapshot()
    lines = []
    for name, data in snapshot['links'].items():
        if not data['connected']:
            status = 'NEPŘIPOJENO / nenalezeno nebo nejednoznačné'
        elif not data['ages']:
            status = 'PORT OTEVŘEN — čekám na platné zprávy'
        else:
            status = ', '.join('{} {}× / {:.1f} s'.format(NAMES.get(kind, kind),
                               data['counts'].get(kind, 0), age)
                               for kind, age in data['ages'].items())
        lines.append('{}  {}\n  {}\n  RX {} B | platné {} | chybné {} | TX {} B{}'.format(
            name, data['device'] or '—', status, data['rx_bytes'], data['valid'],
            data['invalid'], data['tx_bytes'],
            '\n  Chyba: ' + str(data['error']) if data['error'] else ''))
    return '\n\n'.join(lines)


def connection_summary(link):
    identifying = getattr(link, 'identifying', False)
    if identifying:
        candidates, _ = link.candidates()
        rx = 'ČOV: {} · Slave: {}'.format(candidates.get('cov', 'čekám'), candidates.get('slave', 'čekám'))
    else:
        snapshot = link.debug_snapshot()['links']
        def status(role, required):
            item = snapshot[role]
            if not item['connected']:
                return 'NEPŘIPOJENO'
            if all(item['ages'].get(k, float('inf')) <= limit for k, limit in required.items()):
                return 'PŘÍJEM OK'
            return 'CHYBÍ PLATNÁ DATA'
        rx = 'ČOV: {} · Slave: {}'.format(status('cov', {'cov': 30}),
                                         status('slave', {'heating': 3, 'pump': 3}))
    tx = 'TX POVOLENO' if link.transmit_enabled else 'TX VYPNUTO — teploty ani povely se neposílají'
    if link.transmit_enabled and not link.config.get('half_duplex_validated', False):
        tx += ' · poloduplex bez měření'
    return rx + '\n' + tx


class LinkDiagnostics:
    def __init__(self, root, link):
        self.root, self.link = root, link
        self.window = None

    def show(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.lift()
            return
        self.window = tk.Toplevel(self.root)
        self.window.title('Home AS — komunikace RS‑485')
        self.window.geometry('970x540')
        self.window.configure(bg='#222222')
        self.banner = tk.Label(self.window, fg='#ffce76', bg='#222222', justify='left',
                               font=('DejaVu Sans', 11), wraplength=930)
        self.banner.pack(fill='x', padx=12, pady=6)
        self.details = tk.Text(self.window, height=14, font=('DejaVu Sans Mono', 10),
                               bg='#101010', fg='white', wrap='word')
        self.details.pack(fill='both', expand=True, padx=12)
        self.note = tk.Label(self.window, fg='white', bg='#222222', wraplength=930,
                            font=('DejaVu Sans', 10), justify='left')
        self.note.pack(fill='x', padx=12, pady=4)
        self.physical = tk.BooleanVar(value=False)
        if getattr(self.link, 'identifying', False):
            tk.Checkbutton(self.window, variable=self.physical, bg='#222222', fg='white',
                           selectcolor='#333333', text='Potvrzuji: ČOV na CH1, Slave na CH2, Master od obou linek odpojen.').pack()
            self.save_button = tk.Button(self.window, text='Uložit potvrzené přiřazení (TX zůstane vypnuté)',
                                         command=self.save)
            self.save_button.pack(pady=4)
        tk.Button(self.window, text='Zavřít diagnostiku', command=self.window.destroy).pack(pady=4)
        self.refresh()

    def refresh(self):
        if self.window is None or not self.window.winfo_exists():
            return
        self.banner.config(text=connection_summary(self.link) +
            ('\nOdeslaný povel není potvrzené sepnutí; rozhoduje přijatý stav zařízení.'
             if self.link.transmit_enabled else
             '\nBez TX běží původní 40min limity Slave dál; příjem není ověření poloduplexu.'))
        self.details.config(state='normal')
        self.details.delete('1.0', 'end')
        self.details.insert('1.0', diagnostic_text(self.link))
        self.details.config(state='disabled')
        if getattr(self.link, 'identifying', False):
            candidates, reason = self.link.candidates()
            saved = '\nUloženo: ' + self.link.saved_path if self.link.saved_path else ''
            self.note.config(text=reason + saved)
            self.save_button.config(state='normal' if len(candidates) == 2 and self.physical.get() else 'disabled')
        else:
            self.note.config(text='Příjem sledujte i při výpadku regulátoru. '
                'Poloduplex bez měření znamená povolení provozovatelem, nikoli prokázanou nepřítomnost kolizí.')
        self.window.after(500, self.refresh)

    def save(self):
        try:
            path = self.link.save_mapping(self.physical.get())
        except (ValueError, OSError) as exc:
            messagebox.showerror('Přiřazení neuloženo', str(exc), parent=self.window)
            return
        messagebox.showinfo('Přiřazení uloženo',
            path + '\nTX i half_duplex_validated zůstávají false.\n'
            'Po ukončení identifikace spusťte Home AS s touto konfigurací.\n'
            'Aktuální aplikace dál pouze přijímá.', parent=self.window)
