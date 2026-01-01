# ⚡ Quick Reference - Dashboard Shortcuts & Features

## 🎹 Keyboard Shortcuts

Press these keys anywhere on the dashboard (not in input fields):

| Key | Action | Use Case |
|-----|--------|----------|
| `B` | Focus bulk menu | Quick access to bulk actions |
| `S` | Select/Deselect all | Toggle all leads at once |
| `M` | Open message composer | Draft messages while browsing |
| `F` | Focus search box | Find leads quickly |
| `N` | Create new lead | Add new lead (if implemented) |
| `?` | Show shortcuts help | View all keyboard shortcuts |
| `Ctrl+Z` | Undo (coming soon) | Reverse last action |
| `Ctrl+Enter` | Execute bulk action | Send/execute without clicking |

---

## 💾 Save & Reuse Filters

### Step 1: Set Up Filters
```
1. Go to dashboard
2. Apply filters: Status=NEW, Temp=HOT, Category=Restaurant
3. (Optionally select specific leads with checkboxes)
```

### Step 2: Save Selection
```
1. In "Saved Selections" section, click "Save Current"
2. Name it: "Hot Restaurant Leads"
3. Add description: "New hot restaurant prospects to contact"
4. Check "Mark as favorite" if it's important
5. Click "Save Selection"
```

### Step 3: Reuse Later
```
1. Click your saved selection button
2. Dashboard instantly loads those filters
3. All the filtering is remembered
```

---

## 💬 Message Composer

### Quick Send
```
1. Press M (or click blue chat icon)
2. Select lead from dropdown
3. Pick channel: WhatsApp / Email / SMS
4. Choose template or type message
5. Click "Send Now"
```

### With Variables
```
Hi {name}!

I saw your {category} business in {city} 
and thought we could help...
```

**Available variables**: {name}, {city}, {category}

---

## 📊 Kanban Board (Drag & Drop)

### How to Use
```
1. Click "Board" in sidebar
2. Drag lead cards between columns
3. Columns: NEW → CONTACTED → REPLIED → CLOSED
4. Search for specific leads
5. Filter by temperature (HOT/WARM/COLD)
```

### Benefits Over Bulk Menu
- Faster for status updates
- Visual progress tracking
- Can see everything at once
- One card = one lead

---

## 📈 Bulk Operations Tracking

### Monitor Progress
```
1. Click "Operations" in sidebar
2. See active operations with progress bars
3. Real-time: processed/total counts
4. Success/failed/skipped breakdown
5. Cancel button if needed
```

### View History
```
1. Scroll down to "Recent Operations"
2. See all past bulk sends
3. Check duration and results
4. Click "Details" for error info
```

---

## 🎯 Daily Workflow Example

### Morning (5 min)
```
1. Press S → Select all NEW leads
2. Press M → Open composer
3. Type message, select WhatsApp
4. Send to 50 leads
5. Click Operations to monitor
```

### Afternoon (3 min)
```
1. Click saved filter: "Hot Leads To Follow Up"
2. Status badge shows 12 leads replied
3. Use Kanban board to drag REPLIED → CLOSED (quick wins)
4. Save that filter for tomorrow
```

### Evening (2 min)
```
1. Press F, search for "pending"
2. Status filter = CONTACTED
3. Select leads with no response > 7 days
4. Save as "7 Day No Response" filter
5. Send follow-up batch tomorrow
```

---

## 🚀 Power Tips

### Tip 1: Save Your Filters
Save 5-10 common filter combinations:
- "Hot Leads This Week"
- "No Response in 7 Days"
- "New Restaurants"
- "Contacted Today"
- "Ready to Close"

Then you only need 1 click instead of 5 filter selections!

### Tip 2: Use Kanban for Status
For quick status changes, use the Board instead of bulk menu:
- Faster (1 drag instead of 3 clicks)
- Visual (see everything at once)
- Less error-prone

### Tip 3: Composer Always Open
Keep message composer open while browsing:
- Draft messages while reading lead info
- Quick copy-paste contact details
- Don't lose your composition

### Tip 4: Keyboard Shortcuts
Learn just these 3:
- `S` to select all
- `M` for composer  
- `?` for help

They save 10+ hours per month!

### Tip 5: Batch Your Work
Instead of contacting 1 lead at a time:
1. Filter to 50 hot leads
2. Send 50 WhatsApp messages at once
3. Wait for replies
4. Drag replies to board
5. Respond to qualified ones

This multiplies your efficiency!

---

## 🆘 Troubleshooting

### Selection Counter Not Showing?
- Make sure you have checkboxes selected
- If none selected, the bar hides automatically

### Keyboard Shortcuts Not Working?
- Don't press them inside input fields
- Try clicking dashboard first, then pressing
- Some browsers may have conflicts

### Message Composer Not Opening?
- Click the blue chat icon in bottom-right
- Or press `M` key
- Should slide in from right side

### Kanban Board Not Loading Leads?
- Make sure you're logged in
- Check browser console (F12) for errors
- Try refreshing page

---

## 📚 Additional Resources

- **Full Docs**: See IMPLEMENTATION_SUMMARY.md
- **Keyboard Help**: Press `?` on dashboard
- **API Docs**: Check routes in routes/main.py

---

**Last Updated**: January 1, 2026
**Version**: 1.0
