
from dash import Dash, html, dcc, MATCH, State, ALL
import dash_daq as daq
from dash.dependencies import Input, Output

def get_Gauge_from_fieldobject(field_object):
    if(field_object["lower_limit"]) == None:
        lower_limit = field_object["field_gauge_min"]
    else:
        lower_limit = field_object["lower_limit"]
        
    if(field_object["upper_limit"]) == None:
        upper_limit = field_object["field_gauge_max"]
    else:
        upper_limit = field_object["upper_limit"]
    
    try:
        label = field_object["field_label"]
    except KeyError:
        label = field_object["field_name"]
        
    field_name = field_object["field_name"]
    gauge_object = daq.Gauge(
    id={'type': 'gauge',
        'field_name':field_name},
    label=label,
    min=field_object["field_gauge_min"], max=field_object["field_gauge_max"],
    value=0,
    units=field_object["field_gauge_unit"],
    showCurrentValue=True,
    color={
        "gradient": False,
        "ranges": {
            "#F20000":[field_object["field_gauge_min"],lower_limit],
            "green": [lower_limit, upper_limit],
            "#FF0000":[upper_limit,field_object["field_gauge_max"]]
        },
    })
    return gauge_object


def _start_dash_app():
    """Separater Thread für den Dash Webserver."""
    app = Dash(__name__)
    group_divs = []
    with open(r"C:\Users\Orthodrone\AppData\Local\.mavproxy\guard_config.json") as f:
        json_config = json.load(f)
        for message_object in json_config["guarded_messages"]:
            field_divs = []
            for field_object in message_object["fields"]:
                field_divs.append(get_Gauge_from_fieldobject(field_object))
                
            group_divs.append(
                html.Div(children=[
                    html.H2(message_object["message_type"]),
                    html.Div(children=field_divs,style={"display":"flex","flex-direction":"row","align-items":"center"})
                ],style={"align-items":"center"})
            )
    group_divs.append(dcc.Interval(id=("tick"), interval=500, n_intervals=0))
    group_divs.append(html.Meta(httpEquiv="refresh",content="5"))
    #group_divs.append(html.Button('UPDATE', id='tick'))
    app.layout = html.Div(children=group_divs)
    
    @app.callback(
        Output({'type': 'gauge', 'field_name': ALL}, 'value'),
        State({'type': 'gauge', 'field_name': ALL}, 'id'),
        Input('tick', 'n_intervals')    
    )
    def updateGauge(values,ids):
        #print("Updated Gauge Fieldname " + str(id["field_name"]))
        debug_print(values)
        global valuestate
        out = []
        for n,value in enumerate(values):
            debug_print(value["field_name"])
            try:
                out.append(valuestate[value["field_name"]])
            except KeyError:
                #out.append(valuestate[value["value"]])
                out.append(0)
                print("KEY Error: " +  value["field_name"])
        return out

    # WICHTIG: neue Dash Version → app.run()
    app.run(debug=False, port=8050, host="0.0.0.0")