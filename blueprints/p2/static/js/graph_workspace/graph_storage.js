/**
 * Graph Storage Module - Handles loading/saving graph state
 */

window.GraphStorage = (function() {
  let graphId = null;

  function init(fileId) {
    graphId = fileId;
  }

  async function loadGraph() {
    try {
      const response = await fetch(`/graph/${graphId}/data`);
      const data = await response.json();
      
      if (data.ok) {
        const graph = data.graph;
        
        // Load nodes
        if (window.GraphNodes) {
          window.GraphNodes.loadNodes(graph.nodes || []);
        }
        
        // Load edges
        if (window.GraphEdges) {
          window.GraphEdges.loadEdges(graph.edges || []);
        }

        // Load rendered content state from node metadata
        if (window.GraphContentRenderer) {
          window.GraphContentRenderer.loadRendererState(graph.nodes || []);
        }

        // Sync toolbar state (connect/manage/arrow buttons) with latest graph data
        if (window.GraphToolbar?.refreshState) {
          window.GraphToolbar.refreshState();
        }
        
        // Restore viewport state (zoom/pan) from workspace settings
        if (graph.settings && window.GraphCanvas.loadViewportState) {
          window.GraphCanvas.loadViewportState(graph.settings);
        } else {
          window.GraphCanvas.render();
        }
        return graph;
      } else {
        console.error('Failed to load graph:', data.error);
        alert('Failed to load graph data');
      }
    } catch (err) {
      console.error('Error loading graph:', err);
      alert('Error loading graph data');
    }
  }

  async function exportJSONL() {
    try {
      const response = await fetch(`/graph/${graphId}/export/jsonl`);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `graph_${graphId}_export.jsonl`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      } else {
        alert('Export failed');
      }
    } catch (err) {
      console.error('Error exporting graph:', err);
      alert('Error exporting graph');
    }
  }

  return {
    init,
    loadGraph,
    exportJSONL
  };
})();
