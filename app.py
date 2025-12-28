from flask import Flask, request, jsonify
import random
import json
import os
from datetime import datetime

app = Flask(__name__)
MAX_TREASURE_SPEND = 4
# Game state
state = {
    'life': 40,
    'robots': 0,
    'treasures': 0,
    'token_multiplier': 0,
    'lifegain_multiplier': 0,
    'etb_lifegain_sources': 0,
    'barbarian_class_active': False,
    'jackpot_count': 0,
    'event_log': []
}

SAVE_FILE = 'mr_house_save.json'

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/state', methods=['GET'])
def get_state():
    return jsonify(state)

@app.route('/api/spin', methods=['POST'])
def spin():
    data = request.json or {}

    requested_spend = int(data.get('treasures_spent', 0))
    treasures_spent = min(requested_spend, MAX_TREASURE_SPEND)

    # Validate first
    if treasures_spent > state['treasures']:
        return jsonify({'error': 'Not enough treasures'}), 400

    # ✅ DEDUCT IMMEDIATELY
    state['treasures'] -= treasures_spent

    # Dice count: 1 base + 1 per treasure
    num_dice = 1 + treasures_spent

    # Roll dice
    if state['barbarian_class_active']:
        total_rolled = num_dice * 2
        rolls = [random.randint(1, 6) for _ in range(total_rolled)]
        rolls.sort()
        ignored_rolls = rolls[:num_dice]
        dice_rolls = rolls[num_dice:]
    else:
        dice_rolls = [random.randint(1, 6) for _ in range(num_dice)]
        ignored_rolls = []

    # Evaluate rolls
    base_robots = 0
    base_treasures = 0
    hit_count = 0
    jackpot_count = 0
    miss_count = 0

    for die in dice_rolls:
        if die <= 3:
            miss_count += 1
        elif die <= 5:
            hit_count += 1
            base_robots += 1
        else:
            jackpot_count += 1
            base_robots += 1
            base_treasures += 1

    # Outcome
    if jackpot_count > 0:
        outcome = 'JACKPOT'
        state['jackpot_count'] += jackpot_count
    elif hit_count > 0:
        outcome = 'HIT'
    else:
        outcome = 'MISS'

    # Token multiplier (2^mult, allow 0)
    token_mult = 2 ** state['token_multiplier']
    robots_created = base_robots * token_mult
    treasures_created = base_treasures * token_mult

    # Lifegain logic (0-safe)
    if state['etb_lifegain_sources'] > 0:
        base_life = robots_created * state['etb_lifegain_sources']
        life_mult = 2 ** state['lifegain_multiplier']
        life_gained = base_life * life_mult
    else:
        life_gained = 0

    # Apply rewards
    state['robots'] += robots_created
    state['treasures'] += treasures_created
    state['life'] += life_gained

    # Log event
    event = {
        'timestamp': datetime.now().isoformat(),
        'treasures_spent': treasures_spent,
        'dice_rolls': dice_rolls,
        'ignored_rolls': ignored_rolls,
        'outcome': outcome,
        'miss_count': miss_count,
        'hit_count': hit_count,
        'jackpot_count': jackpot_count,
        'robots_created': robots_created,
        'treasures_created': treasures_created,
        'life_gained': life_gained,
    }

    state['event_log'].append(event)

    return jsonify({
        'event': event,
        'state': state
    })

@app.route('/api/modify', methods=['POST'])
def modify():
    data = request.json
    field = data.get('field')
    value = data.get('value')
    
    if field not in ['life', 'robots', 'treasures', 'token_multiplier', 
                     'lifegain_multiplier', 'etb_lifegain_sources']:
        return jsonify({'error': 'Invalid field'}), 400
    
    state[field] = value
    return jsonify(state)

@app.route('/api/toggle_barbarian', methods=['POST'])
def toggle_barbarian():
    state['barbarian_class_active'] = not state['barbarian_class_active']
    return jsonify(state)

@app.route('/api/undo', methods=['POST'])
def undo():
    if not state['event_log']:
        return jsonify({'error': 'Nothing to undo'}), 400
    
    last_event = state['event_log'].pop()
    
    # Revert state changes
    state['robots'] -= last_event['robots_created']
    state['treasures'] -= last_event['treasures_created']
    state['treasures'] += last_event['treasures_spent']  # Refund spent treasures
    state['life'] -= last_event['life_gained']
    
    # Revert jackpot counter
    state['jackpot_count'] -= last_event['jackpot_count']
    
    return jsonify(state)

@app.route('/api/save', methods=['POST'])
def save():
    with open(SAVE_FILE, 'w') as f:
        json.dump(state, f, indent=2)
    return jsonify({'message': 'Saved successfully'})

@app.route('/api/load', methods=['POST'])
def load():
    if not os.path.exists(SAVE_FILE):
        return jsonify({'error': 'No save file found'}), 404
    
    with open(SAVE_FILE, 'r') as f:
        loaded_state = json.load(f)
    
    state.update(loaded_state)
    return jsonify(state)

@app.route('/api/reset', methods=['POST'])
def reset():
    state.update({
        'life': 40,
        'robots': 0,
        'treasures': 0,
        'token_multiplier': 1,
        'lifegain_multiplier': 1,
        'etb_lifegain_sources': 0,
        'barbarian_class_active': False,
        'jackpot_count': 0,
        'event_log': []
    })
    return jsonify(state)

if __name__ == '__main__':
    # Use 0.0.0.0 to allow access from other devices on network
    app.run(host='0.0.0.0', port=5000, debug=True)
