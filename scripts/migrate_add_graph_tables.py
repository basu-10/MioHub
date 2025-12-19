"""Migration script to add graph workspace tables.

Creates graph_workspaces, graph_nodes, graph_edges, graph_node_attachments if missing.
"""
from flask import Flask
from extensions import db
import config
from blueprints.p2.models import GraphWorkspace, GraphNode, GraphEdge, GraphNodeAttachment

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


def main():
    with app.app_context():
        inspector = db.inspect(db.engine)
        existing = set(inspector.get_table_names())
        to_create = {
            'graph_workspaces': GraphWorkspace,
            'graph_nodes': GraphNode,
            'graph_edges': GraphEdge,
            'graph_node_attachments': GraphNodeAttachment,
        }
        created = []
        for table_name, model in to_create.items():
            if table_name not in existing:
                model.__table__.create(db.engine)
                created.append(table_name)
        if created:
            print(f"Created tables: {', '.join(created)}")
        else:
            print("Graph tables already exist; no changes applied.")


if __name__ == '__main__':
    main()
