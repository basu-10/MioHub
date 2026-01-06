"""
Test script to verify graph (MioThink) file send/receive functionality

This script tests that when a graph file is sent to another user:
1. The File record is copied
2. The GraphWorkspace is copied
3. All GraphNodes are copied
4. All GraphEdges are copied with updated references
5. All GraphNodeAttachments are copied with updated references
"""

from flask_app import app
from extensions import db
from blueprints.p2.models import User, File, Folder, GraphWorkspace, GraphNode, GraphEdge, GraphNodeAttachment
from blueprints.p2.folder_ops import copy_file_to_user

def test_graph_copy():
    """Test that graph structures are properly copied when sending files"""
    with app.app_context():
        # Find or create test users
        sender = User.query.filter_by(username='testuser').first()
        receiver = User.query.filter_by(username='testuser222').first()
        
        if not sender or not receiver:
            print("❌ Test users not found. Run this to create them:")
            print("   python -c \"from flask_app import app; from blueprints.p2.models import User; from extensions import db; app.app_context().push(); u1 = User(username='testuser', user_type='user'); u2 = User(username='testuser222', user_type='user'); db.session.add_all([u1, u2]); db.session.commit()\"")
            return False
        
        print(f"✓ Found sender: {sender.username} (ID: {sender.id})")
        print(f"✓ Found receiver: {receiver.username} (ID: {receiver.id})")
        
        # Find an existing graph file or create a test one
        graph_file = File.query.filter_by(
            owner_id=sender.id,
            type='proprietary_graph'
        ).first()
        
        if not graph_file:
            print("\n📝 No existing graph file found. Creating test graph...")
            
            # Create a test graph file
            root_folder = Folder.query.filter_by(
                user_id=sender.id,
                parent_id=None
            ).first()
            
            if not root_folder:
                print("❌ No root folder found for sender")
                return False
            
            graph_file = File(
                owner_id=sender.id,
                folder_id=root_folder.id,
                type='proprietary_graph',
                title='Test Graph for Send/Receive',
                content_json={},
                metadata_json={'description': 'Test graph to verify send functionality'}
            )
            db.session.add(graph_file)
            db.session.flush()
            
            # Create graph workspace
            workspace = GraphWorkspace(
                file_id=graph_file.id,
                owner_id=sender.id,
                folder_id=root_folder.id,
                settings_json={'zoom': 1.0, 'panX': 0, 'panY': 0},
                metadata_json={'test': True}
            )
            db.session.add(workspace)
            db.session.flush()
            
            # Create test nodes
            node1 = GraphNode(
                graph_id=workspace.id,
                title='Node 1',
                summary='First test node',
                position_json={'x': 100, 'y': 100},
                size_json={'w': 200, 'h': 150}
            )
            db.session.add(node1)
            db.session.flush()
            
            node2 = GraphNode(
                graph_id=workspace.id,
                title='Node 2',
                summary='Second test node',
                position_json={'x': 400, 'y': 100},
                size_json={'w': 200, 'h': 150}
            )
            db.session.add(node2)
            db.session.flush()
            
            # Create edge between nodes
            edge = GraphEdge(
                graph_id=workspace.id,
                source_node_id=node1.id,
                target_node_id=node2.id,
                label='connects to',
                edge_type='directed'
            )
            db.session.add(edge)
            
            # Create attachment
            attachment = GraphNodeAttachment(
                node_id=node1.id,
                attachment_type='url',
                url='https://example.com',
                metadata_json={'title': 'Example Link'}
            )
            db.session.add(attachment)
            
            db.session.commit()
            print(f"✓ Created test graph file (ID: {graph_file.id})")
            print(f"  - Workspace ID: {workspace.id}")
            print(f"  - Node 1 ID: {node1.id}")
            print(f"  - Node 2 ID: {node2.id}")
            print(f"  - Edge ID: {edge.id}")
            print(f"  - Attachment ID: {attachment.id}")
        else:
            print(f"\n✓ Found existing graph file: '{graph_file.title}' (ID: {graph_file.id})")
        
        # Get original graph structure counts
        original_workspace = GraphWorkspace.query.filter_by(file_id=graph_file.id).first()
        if not original_workspace:
            print("❌ Graph file exists but has no workspace")
            return False
        
        original_nodes = GraphNode.query.filter_by(graph_id=original_workspace.id).all()
        original_edges = GraphEdge.query.filter_by(graph_id=original_workspace.id).all()
        original_attachments = db.session.query(GraphNodeAttachment).join(
            GraphNode, GraphNodeAttachment.node_id == GraphNode.id
        ).filter(GraphNode.graph_id == original_workspace.id).all()
        
        print(f"\n📊 Original graph structure:")
        print(f"  - Workspace ID: {original_workspace.id}")
        print(f"  - Nodes: {len(original_nodes)}")
        print(f"  - Edges: {len(original_edges)}")
        print(f"  - Attachments: {len(original_attachments)}")
        
        # Perform the copy operation
        print(f"\n🚀 Copying graph file to {receiver.username}...")
        result = copy_file_to_user(graph_file.id, receiver.id, sender_username=sender.username)
        
        if not result or result[0] is None:
            print("❌ Copy operation failed")
            db.session.rollback()
            return False
        
        new_file, bytes_written = result
        db.session.commit()
        
        print(f"✓ File copied successfully (New ID: {new_file.id}, Bytes: {bytes_written})")
        
        # Verify new graph structure
        new_workspace = GraphWorkspace.query.filter_by(file_id=new_file.id).first()
        if not new_workspace:
            print("❌ FAIL: New file has no workspace")
            return False
        
        new_nodes = GraphNode.query.filter_by(graph_id=new_workspace.id).all()
        new_edges = GraphEdge.query.filter_by(graph_id=new_workspace.id).all()
        new_attachments = db.session.query(GraphNodeAttachment).join(
            GraphNode, GraphNodeAttachment.node_id == GraphNode.id
        ).filter(GraphNode.graph_id == new_workspace.id).all()
        
        print(f"\n📊 Copied graph structure:")
        print(f"  - Workspace ID: {new_workspace.id}")
        print(f"  - Nodes: {len(new_nodes)}")
        print(f"  - Edges: {len(new_edges)}")
        print(f"  - Attachments: {len(new_attachments)}")
        
        # Verify counts match
        success = True
        if len(new_nodes) != len(original_nodes):
            print(f"❌ FAIL: Node count mismatch ({len(new_nodes)} vs {len(original_nodes)})")
            success = False
        else:
            print(f"✓ Node count matches: {len(new_nodes)}")
        
        if len(new_edges) != len(original_edges):
            print(f"❌ FAIL: Edge count mismatch ({len(new_edges)} vs {len(original_edges)})")
            success = False
        else:
            print(f"✓ Edge count matches: {len(new_edges)}")
        
        if len(new_attachments) != len(original_attachments):
            print(f"❌ FAIL: Attachment count mismatch ({len(new_attachments)} vs {len(original_attachments)})")
            success = False
        else:
            print(f"✓ Attachment count matches: {len(new_attachments)}")
        
        # Verify ownership
        if new_workspace.owner_id != receiver.id:
            print(f"❌ FAIL: Workspace ownership incorrect ({new_workspace.owner_id} vs {receiver.id})")
            success = False
        else:
            print(f"✓ Workspace ownership correct: {receiver.username}")
        
        # Verify node data integrity
        if len(new_nodes) > 0:
            sample_node = new_nodes[0]
            print(f"\n🔍 Sample node verification:")
            print(f"  - Title: {sample_node.title}")
            print(f"  - Position: {sample_node.position_json}")
            print(f"  - Size: {sample_node.size_json}")
            print(f"  - Graph ID: {sample_node.graph_id} (should be {new_workspace.id})")
            if sample_node.graph_id != new_workspace.id:
                print("❌ FAIL: Node graph_id doesn't match new workspace")
                success = False
            else:
                print("✓ Node graph_id correct")
        
        # Verify edge references
        if len(new_edges) > 0:
            sample_edge = new_edges[0]
            new_node_ids = [n.id for n in new_nodes]
            print(f"\n🔍 Sample edge verification:")
            print(f"  - Source: {sample_edge.source_node_id}")
            print(f"  - Target: {sample_edge.target_node_id}")
            print(f"  - Label: {sample_edge.label}")
            if sample_edge.source_node_id not in new_node_ids:
                print("❌ FAIL: Edge source_node_id doesn't reference new nodes")
                success = False
            elif sample_edge.target_node_id not in new_node_ids:
                print("❌ FAIL: Edge target_node_id doesn't reference new nodes")
                success = False
            else:
                print("✓ Edge references valid")
        
        if success:
            print("\n✅ ALL TESTS PASSED! Graph send/receive is working correctly.")
        else:
            print("\n❌ SOME TESTS FAILED. See errors above.")
        
        return success

if __name__ == '__main__':
    print("=" * 60)
    print("MioThink (Graph) Send/Receive Test")
    print("=" * 60)
    success = test_graph_copy()
    exit(0 if success else 1)
