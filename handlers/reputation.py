from aiogram import Router, types, F
from database import get_setting, verify_user, add_or_update_user
import re
import logging

router = Router()
logger = logging.getLogger(__name__)

# Cache for regex patterns to save DB hits
_patterns = {
    'pos': None,
    'neg': None,
    'black': None,
    'drugs': None
}

async def _get_patterns():
    # Load and compile patterns if not cached
    if not _patterns['pos']:
        pos = await get_setting('positive_keywords', '')
        neg = await get_setting('negative_keywords', '')
        black = await get_setting('blacklist_terms', '')
        drugs = await get_setting('drug_terms', '')
        
        if pos: _patterns['pos'] = re.compile(r'\b(' + '|'.join(re.escape(w.strip()) for w in pos.split(',') if w.strip()) + r')\b', re.I)
        if neg: _patterns['neg'] = re.compile(r'\b(' + '|'.join(re.escape(w.strip()) for w in neg.split(',') if w.strip()) + r')\b', re.I)
        if black: _patterns['black'] = re.compile(r'\b(' + '|'.join(re.escape(w.strip()) for w in black.split(',') if w.strip()) + r')\b', re.I)
        if drugs: _patterns['drugs'] = re.compile(r'\b(' + '|'.join(re.escape(w.strip()) for w in drugs.split(',') if w.strip()) + r')\b', re.I)
    return _patterns

@router.message(F.text)
async def content_guardian(message: types.Message):
    # 1. Check if we are in the White Channel
    white_id = await get_setting('white_channel_id', '0')
    if str(message.chat.id) == white_id:
        enabled = await get_setting('illegal_detection_enabled', '1')
        if enabled == '1':
            patterns = await _get_patterns()
            should_delete = False
            
            # Category A: Counterfeit (Zero Tolerance)
            if patterns['black'] and patterns['black'].search(message.text):
                should_delete = True
            
            # Category B: Drugs (Threshold: 10+ words)
            elif patterns['drugs']:
                drug_matches = patterns['drugs'].findall(message.text)
                if len(drug_matches) > 10:
                    should_delete = True
            
            if should_delete:
                try:
                    await message.delete()
                    warning_tpl = await get_setting('msg_illegal_warning', 'Please be careful of your words.')
                    warning = warning_tpl.format(user_mention=message.from_user.mention_html())
                    await message.answer(warning, parse_mode="HTML")
                    return
                except Exception as e:
                    logger.error(f"Failed to delete illegal message: {e}")

    # 2. Check for Auto-Vouch (if it's a reply)
    if message.reply_to_message and not message.text.startswith('/'):
        enabled = await get_setting('auto_vouch_enabled', '1')
        if enabled != '1': return
        
        # Skip if it's the white channel
        if str(message.chat.id) == white_id: return

        patterns = await _get_patterns()
        text = message.text or ""
        
        # Sentiment Analysis
        has_pos = patterns['pos'].search(text) if patterns['pos'] else False
        has_neg = patterns['neg'].search(text) if patterns['neg'] else False
        
        if has_pos and not has_neg:
            target_id = message.reply_to_message.from_user.id
            await verify_user(target_id, 1, vouched_by=message.from_user.id)
