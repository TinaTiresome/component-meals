import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import pandas as pd
import random
import json
import gunicorn

# Dictionaries to store different components and ingredients
# Seasonality dictionary holds ingredients per season
seasonality = {
    "Spring": ["Asparagus", "Carrots", "Mushrooms", "Turnip", "Okra"],
    "Summer": ["Soy glazed mushrooms", "Avocado", "Asparagus", "Okra", "Sweet Potato", "Carrots", "Broccoli", "Cauliflower",  "Green Beans",  "Green Beans"],
    "Autumn": ["Soy glazed mushrooms", "Sweet Potato", "Carrots", "Broccoli", "Cauliflower", "Squash",  "Green Beans", "Okra"],
    "Winter": ["Soy glazed mushrooms", "Sweet Potato", "Carrots", "Cauliflower", "Turnip", "Squash"]
}

# Components dictionary holds types of components and their possible ingredients
components = {
    "Grains": ["Brown rice", "Quinoa", "Black rice"],
    "Protein": ["Plant based Chicken", "Plant based Beef", "Tofu", "Dehydrated Soy", "Seitan"],
    "Legume": ["Black Beans", "Chickpeas", "Edamame"],
    "Vegetable": list(set(sum(seasonality.values(), []))),
    "Extra": ["Guac", "Corn", "Cucumber", "Peas and Carrots", "Lettuce"]
}


# Initialize the app
app = dash.Dash(__name__)

# Reference the underlying flask app (Used by gunicorn webserver for deployment)
server = app.server

# Dash App layout
app.layout = html.Div([
    html.H1('Meal Plan Generator'),
    html.P('My partner does all the cooking, and to help him with the mental load I have long wanted to make a tool like this. \
           So, this is pretty buggy, but it makes meal planning and prepping easier anyway! \
               Also, I decided to not include a sauce, because it introduced to many insane combinations.'),
    html.P('Changing either of the Selections will regenerate the whole table!'),
    html.Div([
        html.Div([
            html.H2('Selections'),
            dcc.Dropdown(id='season-dropdown', options=[
                {'label': i, 'value': i} for i in seasonality.keys()
            ], placeholder="Select season", style={'width': '100%'}),

            dcc.Dropdown(id='day-dropdown', options=[
                {'label': f'{i} days', 'value': i} for i in range(1, 8)
            ], value=6, placeholder="Select number of days", style={'width': '100%'}),
        ], style={'width': '40%', 'display': 'inline-block'}),

        html.Div([
            html.H2('Ingredients'),
            dcc.Dropdown(id='category-dropdown', options=[
                {'label': i, 'value': i} for i in components.keys()
            ], placeholder="Select category to add/remove ingredients"),

            dcc.Input(id='add-ingredient', type='text',
                      placeholder='Add a new ingredient'),
            html.Button('Submit', id='submit-ingredient', n_clicks=0),

            dcc.Input(id='remove-ingredient', type='text',
                      placeholder='Remove an ingredient'),
            html.Button('Remove', id='remove-button', n_clicks=0),
        ], style={'width': '40%', 'display': 'inline-block', 'float': 'right'}),
    ], style={'width': '100%'}),

    html.Div(id='output-table'),
    html.Button('Generate Grocery List',
                id='generate-grocery-list', n_clicks=0),
    html.Div(id='output-grocery-list', style={'width': '50%'}),

    # Hidden div to store meal plan and grocery list
    html.Div(id='hidden-div', style={'display': 'none'}),
])


@app.callback(
    Output('output-table', 'children'),
    Output('hidden-div', 'children'),
    [Input('submit-ingredient', 'n_clicks'),
     Input('remove-button', 'n_clicks'),
     Input('day-dropdown', 'value'),
     Input('season-dropdown', 'value')],
    [State('add-ingredient', 'value'),
     State('remove-ingredient', 'value'),
     State('category-dropdown', 'value')]
)
def update_meal_plan(add_clicks, remove_clicks, days, season, ingredient_to_add, ingredient_to_remove, selected_category):
    """
    This function updates the meal plan when there are changes in the inputs. It adds or removes ingredients based
    on user actions. Then it randomly selects ingredients from the components and creates a meal plan and grocery list.
    """
    if ingredient_to_add and add_clicks and selected_category:
        components[selected_category].append(ingredient_to_add)

    if ingredient_to_remove and remove_clicks and selected_category:
        if ingredient_to_remove in components[selected_category]:
            components[selected_category].remove(ingredient_to_remove)

    vegetables = seasonality.get(season, [])

    meal_plan = {}
    grocery_list = {}

    grains = random.sample(components["Grains"], 2)
    veg_items = random.sample([0, 0, 1, 1, 2, 2], k=days)
    random.shuffle(veg_items)

    grain_items = random.sample([0, 0, 0, 1, 1, 1], k=days)
    random.shuffle(grain_items)

    for day in range(days):
        meal_plan[day] = {}
        for component, options in components.items():
            if component == "Vegetable":
                chosen = random.choice(vegetables) if vegetables else None
            elif component == "Grains":
                chosen = grains[grain_items[day]]
            else:
                chosen = random.choice(options)
            meal_plan[day][component] = chosen

            if chosen not in grocery_list:
                grocery_list[chosen] = [day + 1]
            else:
                grocery_list[chosen].append(day + 1)

    meal_plan_df = pd.DataFrame(meal_plan).T
    grocery_list_records = [{'Grocery List': k, 'Days': ', '.join(
        map(str, v))} for k, v in grocery_list.items()]

    meal_plan_table = dash_table.DataTable(
        data=meal_plan_df.to_dict('records'),
        columns=[{'name': i, 'id': i} for i in meal_plan_df.columns],
        editable=True,
        style_cell={'minWidth': '180px', 'width': '180px', 'maxWidth': '180px'}
    )

    stored_data = json.dumps(
        {'meal_plan': meal_plan_df.to_dict(), 'grocery_list': grocery_list_records})

    return meal_plan_table, stored_data


@app.callback(
    Output('output-grocery-list', 'children'),
    [Input('generate-grocery-list', 'n_clicks')],
    [State('hidden-div', 'children')]
)
def generate_grocery_list(n_clicks, stored_data):
    """
    This function generates the grocery list when the 'Generate Grocery List' button is clicked.
    It uses the stored data (meal plan and grocery list) from the hidden div to generate the list.
    """
    if n_clicks > 0 and stored_data is not None:
        data = json.loads(stored_data)
        grocery_list_records = data['grocery_list']

        grocery_list_table = dash_table.DataTable(
            data=grocery_list_records,
            columns=[{'name': i, 'id': i}
                     for i in grocery_list_records[0].keys()],
            editable=True,
            style_cell={'minWidth': '100px',
                        'width': '100px', 'maxWidth': '180px'}
        )

        return grocery_list_table

    return None


# Start the Dash app server
if __name__ == "__main__":
    app.run_server(debug=False, host='0.0.0.0', port=8050)
