Order Splitter – Django Expense Management App

Order Splitter is a Django-based web application designed to manage and split shared expenses across multiple sessions (e.g. group orders, dinners, events). The app allows users to create sessions, add participants, assign items with quantities and prices, and automatically calculate per-person totals including tax, service, and discounts.

The project was built with a strong focus on clean architecture, scalability, and real-world usability.

Key Features

Session-based expense grouping

Per-person item management (name, quantity, price)

Automatic total calculations per person

Session-level tax, service, and discount handling

Detailed and summarized session views for easy sharing

Class-based views (CBVs) with clean URL design

Reusable templates and partials (base layout, navbars)

Server-side rendering using Django templates

Technical Highlights

Django (CBVs: ListView, DetailView, CreateView, UpdateView, DeleteView)

Relational data modeling (Session → Person → Item)

URL namespacing and dynamic routing

Template inheritance and partial templates

Form handling and validation

Production-aware setup (DEBUG handling, ALLOWED_HOSTS, static files)

Designed to be easily extended with authentication and PostgreSQL

Use Cases

Splitting restaurant bills

Group orders and shared purchases

Event or trip expense tracking