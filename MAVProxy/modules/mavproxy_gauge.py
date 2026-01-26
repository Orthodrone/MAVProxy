# gauge.py
from __future__ import annotations

"""
MAVProxy Modul: gauge
Zeigt z.B. Groundspeed per Dash-Gauge im Browser an.
Start:   mavproxy.py --master=... --load gauge
"""

import threading
import queue

from MAVProxy.modules.lib import mp_module

from dash import Dash, html, dcc
import dash_daq as daq
from dash.dependencies import Input, Output

# Thread-sichere Queue MAVProxy → Dash
_gauge_queue = queue.Queue()


def _start_dash_app():
    """Separater Thread für den Dash Webserver."""
    app = Dash(__name__)

    app.layout = html.Div([
        html.H2("MAVProxy Gauge"),
        html.Div("Groundspeed (m/s) aus MAVLink VFR_HUD"),
        daq.Gauge(
            id="gs-gauge",
            label="Groundspeed",
            min=0, max=50,
            value=0,
            units="m/s",
            showCurrentValue=True,
            color={
                "gradient": True,
                "ranges": {
                    "green": [5, 20],
                    "yellow": [20, 30],
                    "red": [30, 50],
                },
            },
        ),
        dcc.Interval(id="tick", interval=500, n_intervals=0),
    ])

    @app.callback(
        Output("gs-gauge", "value"),
        Input("tick", "n_intervals"),
    )
    def update(_n):
        """Wird regelmäßig aufgerufen, holt letzten Wert aus Queue."""
        val = None
        try:
            while True:
                val = _gauge_queue.get_nowait()
        except queue.Empty:
            pass

        return 0 if val is None else float(val)

    # WICHTIG: neue Dash Version → app.run()
    app.run(debug=False, port=8050, host="0.0.0.0")


class GaugeModule(mp_module.MPModule):
    """MAVProxy gauge Modul"""
    def __init__(self, mpstate):
        super(GaugeModule, self).__init__(mpstate, "gauge", "Gauge Anzeige Modul")

        self.console.writeln("Gauge: Starte Dash Webserver auf http://localhost:8050 ...")
        self._dash_thread = threading.Thread(target=_start_dash_app, daemon=True)
        self._dash_thread.start()

        self.last_gs = 0.0

    def mavlink_packet(self, m):
        """Wird für jedes eingehende MAVLink-Message aufgerufen."""
        if m.get_type() == "VFR_HUD":
            gs = getattr(m, "groundspeed", None)
            if gs is not None:
                self.last_gs = gs
                try:
                    _gauge_queue.put_nowait(gs)
                except queue.Full:
                    pass

    def unload(self):
        self.console.writeln("Gauge: Modul entladen. Dash-Server läuft weiter bis MAVProxy beendet wird.")
        super(GaugeModule, self).unload()

    def idle_task(self):
        pass


def init(mpstate):
    """Initialisierung des Moduls."""
    return GaugeModule(mpstate)
