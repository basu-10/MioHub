(function () {
  const START_POSITION = 15;
  const SPACING = 12;
  const DATED_CARD_WIDTH = 150;
  const UNDATED_CARD_WIDTH = 210;

  function ensureEventOrder(timeline) {
    if (!timeline || !Array.isArray(timeline.events)) return;
    timeline.events = timeline.events
      .slice()
      .sort((a, b) => {
        const ao = a.order ?? a.position ?? 0;
        const bo = b.order ?? b.position ?? 0;
        return ao - bo;
      })
      .map((ev, idx) => ({ ...ev, order: idx }));
  }

  function positionTimelineEvents(timeline, options = {}) {
    if (!timeline || !Array.isArray(timeline.events)) return;

    const preserveUndatedPositions = options.preserveUndatedPositions || false;

    ensureEventOrder(timeline);

    const orderedEvents = timeline.events;

    // Simple sequential positioning: all events placed left-to-right based on order
    let currentX = START_POSITION;

    orderedEvents.forEach((event, idx) => {
      const width = event.date ? DATED_CARD_WIDTH : UNDATED_CARD_WIDTH;

      if (!event.date && preserveUndatedPositions && event.position !== undefined) {
        // Preserve existing undated event positions if requested
        // (used on initial load to avoid shifting user-placed events)
      } else {
        // Position sequentially: dated and undated events both use order-based placement
        event.position = currentX;
      }

      currentX = event.position + width + SPACING;
    });

    // Update order field to match final positions
    orderedEvents.forEach((ev, idx) => {
      ev.order = idx;
    });

    timeline.events = orderedEvents;
  }

  function determineInsertionIndex(timeline, dropX, draggedEventId) {
    if (!timeline || !Array.isArray(timeline.events)) return 0;
    
    // Sort by order field (or position fallback), keep dragged event for proper indexing
    const sortedEvents = timeline.events
      .slice()
      .sort((a, b) => (a.order ?? a.position ?? 0) - (b.order ?? b.position ?? 0));

    for (let i = 0; i < sortedEvents.length; i += 1) {
      const event = sortedEvents[i];
      // Skip the dragged event itself
      if (event.id === draggedEventId) continue;
      
      const width = event.date ? DATED_CARD_WIDTH : UNDATED_CARD_WIDTH;
      const midpoint = (event.position ?? START_POSITION) + width / 2;
      if (dropX < midpoint) {
        // Return the actual index in the sorted array
        return i;
      }
    }

    return sortedEvents.length;
  }

  function calculateIndicatorPosition(timeline, insertionIndex) {
    if (!timeline || !Array.isArray(timeline.events)) return START_POSITION;
    const events = timeline.events.slice().sort((a, b) => (a.position ?? 0) - (b.position ?? 0));

    if (events.length === 0) return START_POSITION;

    if (insertionIndex <= 0) {
      return Math.max(START_POSITION, (events[0].position ?? START_POSITION) - SPACING / 2);
    }

    if (insertionIndex >= events.length) {
      const last = events[events.length - 1];
      const lastWidth = last.date ? DATED_CARD_WIDTH : UNDATED_CARD_WIDTH;
      return (last.position ?? START_POSITION) + lastWidth + SPACING / 2;
    }

    const prev = events[insertionIndex - 1];
    const prevWidth = prev.date ? DATED_CARD_WIDTH : UNDATED_CARD_WIDTH;
    return (prev.position ?? START_POSITION) + prevWidth + SPACING / 2;
  }

  /**
   * Detect chronological order violations
   * Returns array of warnings for dated events that appear in wrong order
   */
  function detectChronologicalIssues(timeline) {
    if (!timeline || !Array.isArray(timeline.events)) return [];
    
    const warnings = [];
    const datedEvents = timeline.events.filter(e => e.date).sort((a, b) => a.order - b.order);
    
    if (datedEvents.length < 2) return warnings;
    
    // Check for chronological order violations
    for (let i = 0; i < datedEvents.length - 1; i++) {
      const current = datedEvents[i];
      const next = datedEvents[i + 1];
      
      const currentDate = new Date(current.date).getTime();
      const nextDate = new Date(next.date).getTime();
      
      // Check if later date appears before earlier date visually
      if (currentDate > nextDate) {
        warnings.push({
          eventId: next.id,
          type: 'chronology-violation',
          message: `Event date ${formatDateShort(next.date)} appears after ${formatDateShort(current.date)} but should be earlier`
        });
      }
    }
    
    return warnings;
  }
  
  /**
   * Smart insert/update of a dated event - maintains chronological order among dated events
   * while preserving positions of all undated events and other dated events
   * @param {Object} timeline - Timeline object with events array
   * @param {string} eventId - ID of the event being updated/added
   */
  function smartInsertDatedEvent(timeline, eventId) {
    if (!timeline || !Array.isArray(timeline.events)) return;
    
    const targetEvent = timeline.events.find(e => e.id === eventId);
    if (!targetEvent || !targetEvent.date) return; // Only for dated events
    
    // Remove target event temporarily
    const otherEvents = timeline.events.filter(e => e.id !== eventId);
    
    // Find where to insert among dated events chronologically
    const datedEvents = otherEvents.filter(e => e.date);
    const targetDate = new Date(targetEvent.date).getTime();
    
    // Find correct position: after last dated event with earlier/equal date
    let insertIndex = 0;
    for (let i = 0; i < otherEvents.length; i++) {
      const ev = otherEvents[i];
      if (ev.date) {
        const evDate = new Date(ev.date).getTime();
        if (evDate <= targetDate) {
          insertIndex = i + 1; // Insert after this dated event
        }
      }
    }
    
    // Insert at calculated position
    otherEvents.splice(insertIndex, 0, targetEvent);
    
    // Update timeline with new order
    timeline.events = otherEvents;
    timeline.events.forEach((ev, idx) => {
      ev.order = idx;
    });
  }
  
  /**
   * Fix chronological order by reordering events to maintain date sequence
   * DEPRECATED: Use smartInsertDatedEvent instead for preserving undated positions
   */
  function fixChronologicalOrder(timeline) {
    if (!timeline || !Array.isArray(timeline.events)) return false;
    
    const datedEvents = timeline.events.filter(e => e.date).sort((a, b) => new Date(a.date) - new Date(b.date));
    const undatedEvents = timeline.events.filter(e => !e.date);
    
    if (datedEvents.length === 0) return false;
    
    // Strategy: Place all undated events first, then dated events in chronological order
    // This ensures dated events maintain chronological sequence without overlap issues
    const reordered = [...undatedEvents, ...datedEvents];
    
    // Update the timeline events with new order
    timeline.events = reordered;
    
    // Update order fields
    timeline.events.forEach((ev, idx) => {
      ev.order = idx;
    });
    
    return true;
  }
  
  /**
   * Format date for short display in warnings
   */
  function formatDateShort(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  window.TimelinePositioning = {
    ensureEventOrder,
    positionTimelineEvents,
    determineInsertionIndex,
    calculateIndicatorPosition,
    detectChronologicalIssues,
    smartInsertDatedEvent,
    fixChronologicalOrder, // Deprecated
    constants: {
      START_POSITION,
      SPACING,
      DATED_CARD_WIDTH,
      UNDATED_CARD_WIDTH,
    },
  };
})();
