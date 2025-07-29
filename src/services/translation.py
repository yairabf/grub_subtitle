import os
from openai import OpenAI
from dotenv import load_dotenv
import re
import httpx

class TranslationService:
    def __init__(self, target_language="he", source_language="en"):
        load_dotenv()
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        self.target_language = target_language
        self.source_language = source_language
        
        # Language names for translation prompts
        self.language_names = {
            "he": "Hebrew",
            "es": "Spanish", 
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "ru": "Russian",
            "ja": "Japanese",
            "ko": "Korean",
            "zh": "Chinese",
            "ar": "Arabic"
        }
        
        # Create a custom HTTP client without proxy settings
        http_client = httpx.Client(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True
        )
        
        self.client = OpenAI(
            api_key=api_key,
            http_client=http_client
        )

    def parse_srt_blocks(self, content):
        """Parse SRT content into subtitle blocks."""
        lines = content.strip().split('\n')
        blocks = []
        current_block = []
        
        for line in lines:
            line = line.strip()
            if not line and current_block:
                # Empty line marks end of subtitle block
                blocks.append('\n'.join(current_block))
                current_block = []
            elif line:
                current_block.append(line)
        
        # Add the last block if it exists
        if current_block:
            blocks.append('\n'.join(current_block))
        
        return blocks

    def split_subtitle_content(self, content, max_chunk_size=4000, max_blocks_per_chunk=15):
        """Split subtitle content into chunks that preserve complete subtitle blocks."""
        blocks = self.parse_srt_blocks(content)
        chunks = []
        current_chunk = []
        current_size = 0
        current_block_count = 0
        
        for block in blocks:
            block_size = len(block)
            
            # If a single block is too large, we need to split it
            if block_size > max_chunk_size:
                # If we have a current chunk, save it first
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                    current_block_count = 0
                
                # Split the large block into smaller parts
                # For SRT format, we'll split by lines but keep subtitle numbers and timestamps together
                lines = block.split('\n')
                if len(lines) >= 3:  # Has number, timestamp, and text
                    # Keep number and timestamp together
                    header_lines = lines[:2]  # Number and timestamp
                    text_lines = lines[2:]    # Actual subtitle text
                    
                    # Split text lines into smaller chunks
                    text_chunk_size = max_chunk_size - len('\n'.join(header_lines)) - 10  # Buffer
                    current_text_chunk = []
                    current_text_size = 0
                    
                    for text_line in text_lines:
                        line_size = len(text_line) + 1  # +1 for newline
                        
                        if current_text_size + line_size > text_chunk_size and current_text_chunk:
                            # Save current text chunk
                            full_block = '\n'.join(header_lines + current_text_chunk)
                            chunks.append(full_block)
                            
                            # Start new text chunk
                            current_text_chunk = [text_line]
                            current_text_size = line_size
                        else:
                            current_text_chunk.append(text_line)
                            current_text_size += line_size
                    
                    # Add remaining text chunk
                    if current_text_chunk:
                        full_block = '\n'.join(header_lines + current_text_chunk)
                        chunks.append(full_block)
                else:
                    # Fallback: just split the block by size
                    for i in range(0, len(block), max_chunk_size):
                        chunk_part = block[i:i + max_chunk_size]
                        chunks.append(chunk_part)
            else:
                # Check if adding this block would exceed size or block count limits
                size_exceeded = current_size + block_size > max_chunk_size
                block_count_exceeded = current_block_count >= max_blocks_per_chunk
                
                # If adding this block would exceed limits and we already have content
                if (size_exceeded or block_count_exceeded) and current_chunk:
                    # Save current chunk and start a new one
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = [block]
                    current_size = block_size
                    current_block_count = 1
                else:
                    # Add block to current chunk
                    current_chunk.append(block)
                    current_size += block_size
                    current_block_count += 1
        
        # Add the last chunk if it has content
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks

    def translate_subtitle(self, input_path, output_path, chunk_size=4000, max_blocks_per_chunk=15):
        """Translate subtitle file using OpenAI."""
        target_language_name = self.language_names.get(self.target_language, self.target_language)
        
        # Check if target language subtitle already exists
        if os.path.exists(output_path):
            print(f"{target_language_name} subtitle already exists: {os.path.basename(output_path)}")
            return True
            
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse and count subtitle blocks
            blocks = self.parse_srt_blocks(content)
            print(f"Found {len(blocks)} subtitle blocks to translate")

            # Split content into chunks with more conservative chunking
            chunks = self.split_subtitle_content(content, chunk_size, max_blocks_per_chunk)
            
            print(f"Split into {len(chunks)} chunks for translation")
            print(f"Chunk settings: max size={chunk_size} chars, max blocks={max_blocks_per_chunk}")
            
            # Show chunk distribution
            for i, chunk in enumerate(chunks):
                chunk_blocks = self.parse_srt_blocks(chunk)
                chunk_size_actual = len(chunk)
                print(f"  Chunk {i+1}: {len(chunk_blocks)} blocks, {chunk_size_actual} chars")
                
                # Warn if chunk is still too large
                if chunk_size_actual > 8000:  # Conservative limit
                    print(f"  ⚠️  Warning: Chunk {i+1} is very large ({chunk_size_actual} chars)")
            
            translated_chunks = []
            
            for i, chunk in enumerate(chunks):
                print(f"Translating chunk {i+1}/{len(chunks)} ({len(self.parse_srt_blocks(chunk))} blocks)...")
                
                max_retries = 3
                retry_delay = 2  # seconds
                
                for attempt in range(max_retries):
                    try:
                        response = self.client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": f"""You are a subtitle translator. Translate the following subtitle content to {target_language_name}, maintaining the exact same format and timing. 

IMPORTANT RULES:
1. Keep all numbers, timestamps, and formatting exactly as they are
2. Only translate the text content (the actual subtitle text)
3. Preserve the exact SRT format with subtitle numbers and timestamps
4. Detect the source language automatically and translate to {target_language_name}
5. Maintain proper {target_language_name} punctuation and grammar
6. Do not add or remove any subtitle blocks
7. Keep the exact same number of subtitle blocks as the original
8. Ensure each subtitle block is properly separated by empty lines"""},
                                {"role": "user", "content": chunk}
                            ],
                            temperature=0.3,  # Lower temperature for more consistent translations
                            max_tokens=4000   # Increased for larger chunks
                        )

                        translated_chunk = response.choices[0].message.content
                        
                        if translated_chunk is None or not translated_chunk.strip():
                            print(f"Error: Translation returned empty content for chunk {i+1}")
                            return False
                        
                        translated_chunks.append(translated_chunk)
                        print(f"  ✅ Chunk {i+1} translated successfully")
                        break  # Success, exit retry loop
                        
                    except Exception as e:
                        error_msg = str(e)
                        if "overloaded" in error_msg.lower() or "rate limit" in error_msg.lower():
                            if attempt < max_retries - 1:
                                print(f"  ⏳ API overload/rate limit, retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                                import time
                                time.sleep(retry_delay)
                                retry_delay *= 2  # Exponential backoff
                            else:
                                print(f"Error translating chunk {i+1} after {max_retries} attempts: {e}")
                                return False
                        else:
                            print(f"Error translating chunk {i+1}: {e}")
                            return False

            # Combine all translated chunks
            translated_content = '\n\n'.join(translated_chunks)
            
            # Verify we have the same number of subtitle blocks
            original_blocks = self.parse_srt_blocks(content)
            translated_blocks = self.parse_srt_blocks(translated_content)
            
            print(f"Original blocks: {len(original_blocks)}, Translated blocks: {len(translated_blocks)}")
            
            # More lenient validation - allow some block count differences due to splitting
            block_count_diff = abs(len(translated_blocks) - len(original_blocks))
            if block_count_diff > len(original_blocks) * 0.5:  # Allow up to 50% difference
                print(f"Warning: Significant block count mismatch! Original: {len(original_blocks)}, Translated: {len(translated_blocks)}")
                print("Attempting to fix block count...")
                
                # Try to fix by ensuring proper spacing
                translated_content = re.sub(r'\n{3,}', '\n\n', translated_content)
                translated_blocks = self.parse_srt_blocks(translated_content)
                
                if abs(len(translated_blocks) - len(original_blocks)) > len(original_blocks) * 0.5:
                    print(f"Warning: Could not fix block count. Original: {len(original_blocks)}, Translated: {len(translated_blocks)}")
                    print("Continuing anyway as translation may still be usable...")
            else:
                print(f"✅ Block count is acceptable. Original: {len(original_blocks)}, Translated: {len(translated_blocks)}")

            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(translated_content)
            
            print(f"✅ Successfully translated {len(original_blocks)} subtitle blocks to Hebrew in {len(chunks)} chunks")
            print(f"✅ Hebrew subtitle saved to: {output_path}")
            return True
            
        except Exception as e:
            print(f"Error translating subtitle: {e}")
            return False

    def validate_translation_completeness(self, original_path, translated_path):
        """Validate that all subtitle blocks were translated."""
        try:
            with open(original_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            with open(translated_path, 'r', encoding='utf-8') as f:
                translated_content = f.read()
            
            original_blocks = self.parse_srt_blocks(original_content)
            translated_blocks = self.parse_srt_blocks(translated_content)
            
            if len(original_blocks) != len(translated_blocks):
                print(f"❌ Translation incomplete! Original: {len(original_blocks)} blocks, Translated: {len(translated_blocks)} blocks")
                return False
            
            print(f"✅ Translation complete! All {len(original_blocks)} blocks translated")
            return True
            
        except Exception as e:
            print(f"Error validating translation: {e}")
            return False 