import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum
from mousetube_api.models import PageView

LOGS_DIR = "logs/"


class Command(BaseCommand):
    help = "Export page views to a static HTML report"

    def handle(self, *args, **kwargs):
        year = timezone.now().year
        filename = f"stats_{year}.html"
        output_path = os.path.join(LOGS_DIR, filename)

        # Get all visites for the current year
        views = PageView.objects.filter(date__year=year).order_by("date")

        # Organize data by date and path for easy filtering
        data = [
            {"path": view.path, "date": view.date.isoformat(), "count": view.count}
            for view in views
        ]

        # Extract all unique pages for the page selector
        pages = list(set(view["path"] for view in data))

        # If you choose "All pages", group by date and add up the visits
        total_data = []
        for view in views.values("date").annotate(total_visits=Sum("count")):
            total_data.append(
                {"date": view["date"].isoformat(), "count": view["total_visits"]}
            )

        with open(output_path, "w") as f:
            f.write(self.render_html(data, year, pages, total_data))

        # Save a "latest" file for the most recent page
        latest_path = os.path.join(LOGS_DIR, "latest.html")
        with open(latest_path, "w") as f:
            f.write(self.render_html(data, year, pages, total_data))

        self.stdout.write(self.style.SUCCESS(f"Exported stats to {output_path}"))

    def render_html(self, data, year, pages, total_data):
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <link rel="icon" href="https://avatars.githubusercontent.com/u/150816394?v=4" type="image/x-icon">
    <title>Page Views Stats {year}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<header>
    <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 50px;">
    <img src="https://avatars.githubusercontent.com/u/150816394?v=4" alt="Logo" style="width: 100px; height: 100px; margin-right: 50px;">
    <h1>Stats Visites - {year}</h1>
    </div>
</header>
<body>
<!-- Page selector -->
<label for="page">Select a page:</label>
<select id="page" style="margin-right: 20px;">
    <option value="all">All pages</option>
    {"".join([f'<option value="{page}">{page}</option>' for page in pages])}
</select>

<!-- Date selector -->
<label for="date-range">Select a period:</label>
<input type="date" id="start-date"> à
<input type="date" id="end-date">

<div style="display: flex; justify-content: center; align-items: center; max-width: 70%; margin-top: 50px;">
    <canvas id="chart"></canvas>
</div>

<script>
const rawData = {data};
const totalData = {total_data};

function filterData(startDate, endDate, selectedPage) {{
    let filteredData = selectedPage === 'all' ? totalData : rawData;

    if (selectedPage !== 'all') {{
        filteredData = filteredData.filter(row => row.path === selectedPage);
    }}

    if (startDate) {{
        filteredData = filteredData.filter(row => new Date(row.date) >= new Date(startDate));
    }}

    if (endDate) {{
        filteredData = filteredData.filter(row => new Date(row.date) <= new Date(endDate));
    }}

    return filteredData;
}}

const ctx = document.getElementById('chart').getContext('2d');
let chart = new Chart(ctx, {{
    type: 'line',
    data: {{
        labels: [],
        datasets: [{{
            label: 'Number of visites',
            data: [],
            fill: false,
            borderColor: 'rgb(219, 98, 98)',
            tension: 0.1
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{
            legend: {{ position: 'bottom' }},
            title: {{ display: true, text: 'Page Views Stats' }}
        }},
    }}
}});

function updateChart() {{
    const startDate = document.getElementById('start-date').value;
    const endDate = document.getElementById('end-date').value;
    const selectedPage = document.getElementById('page').value;

    const data = filterData(startDate, endDate, selectedPage);
    const labels = data.map(row => row.date);
    const counts = data.map(row => row.count);

    chart.data.labels = labels;
    chart.data.datasets[0].data = counts;
    chart.update();
}}

// Set the default period to the last 7 days when the page loads
document.getElementById('start-date').value = getDateNDaysAgo(7);
document.getElementById('end-date').value = getTodayDate();
updateChart();

document.getElementById('page').addEventListener('change', updateChart);
document.getElementById('start-date').addEventListener('change', updateChart);
document.getElementById('end-date').addEventListener('change', updateChart);

// Function to get the date n days ago
function getDateNDaysAgo(n) {{
    const today = new Date();
    today.setDate(today.getDate() - n);
    return today.toISOString().split('T')[0];  // returns the date in YYYY-MM-DD format
}}

// Function to get today's date
function getTodayDate() {{
    const today = new Date();
    return today.toISOString().split('T')[0];  // returns the date in YYYY-MM-DD format
}}

</script>
</body>
</html>
"""
