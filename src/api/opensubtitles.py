import os
import xmlrpc.client
import base64
import gzip
import time
from dotenv import load_dotenv

class OpenSubtitlesAPI:
    def __init__(self, username=None, password=None):
        load_dotenv()
        self.username = username or os.getenv('OPENSUBTITLES_USERNAME')
        self.password = password or os.getenv('OPENSUBTITLES_PASSWORD')
        self.server = xmlrpc.client.ServerProxy('https://api.opensubtitles.org/xml-rpc')
        self.token = None
        self.user_agent = "VLSub"
        self._login()

    def _login(self):
        """Login to OpenSubtitles and get session token."""
        try:
            print(f"[DEBUG] Logging in with username: {self.username}")
            response = self.server.LogIn(
                self.username, 
                self.password, 
                'en', 
                self.user_agent
            )
            print(f"[DEBUG] Login response: {response}")
            
            # Check if we got a token, even if status is not 200 OK
            if isinstance(response, dict) and response.get('token'):
                self.token = response.get('token')
                print(f"[DEBUG] Successfully logged in, token received: {self.token}")
                return True
            else:
                print(f"[DEBUG] Login failed: {response}")
                return False
        except Exception as e:
            print(f"Error during login: {e}")
            return False

    def _ensure_logged_in(self):
        """Ensure we have a valid token, re-login if needed."""
        if not self.token:
            self._login()

    def search_subtitles(self, query, language='eng', season=None, episode=None, max_pages=10):
        """Search for subtitles using XML-RPC API."""
        self._ensure_logged_in()
        print(f"[DEBUG] Searching for: '{query}' in language: '{language}'")
        if season and episode:
            print(f"[DEBUG] Including season {season}, episode {episode} in search")
        
        # Prepare search parameters
        search_params = [{
            'sublanguageid': language,
            'query': query,
            'season': season,
            'episode': episode
        }]
        
        print(f"[DEBUG] Search params: {search_params}")
        
        try:
            response = self.server.SearchSubtitles(self.token, search_params)
            print(f"[DEBUG] Search response status: {response.get('status') if isinstance(response, dict) else 'Unknown'}")
            
            if isinstance(response, dict) and response.get('status') == '200 OK' and response.get('data'):
                results = response['data']
                print(f"[DEBUG] Found {len(results)} results")
                
                # Convert to the same format as the REST API for compatibility
                converted_results = []
                for result in results:
                    converted_result = {
                        'id': result.get('IDSubtitleFile'),
                        'type': 'subtitle',
                        'attributes': {
                            'subtitle_id': result.get('IDSubtitle'),
                            'language': result.get('SubLanguageID'),
                            'download_count': int(result.get('SubDownloadsCnt', 0)),
                            'new_download_count': int(result.get('SubDownloadsCnt', 0)),
                            'hearing_impaired': result.get('SubHearingImpaired') == '1',
                            'hd': result.get('SubHD') == '1',
                            'fps': float(result.get('MovieFPS', 0)),
                            'upload_date': result.get('SubAddDate'),
                            'release': result.get('SubFileName'),
                            'comments': result.get('SubComments'),
                            'feature_details': {
                                'feature_id': result.get('IDMovie'),
                                'feature_type': 'Episode',
                                'year': int(result.get('MovieYear', 0)),
                                'title': result.get('MovieName'),
                                'movie_name': result.get('MovieName'),
                                'imdb_id': result.get('IDMovieImdb'),
                                'season_number': int(result.get('SeriesSeason', 0)),
                                'episode_number': int(result.get('SeriesEpisode', 0)),
                                'parent_title': result.get('MovieName')
                            },
                            'files': [{
                                'file_id': result.get('IDSubtitleFile'),
                                'cd_number': 1,
                                'file_name': result.get('SubFileName')
                            }]
                        }
                    }
                    converted_results.append(converted_result)
                
                return converted_results
            else:
                print(f"[DEBUG] No results found or error: {response}")
                return []
                
        except Exception as e:
            print(f"Error searching subtitles: {e}")
            return []

    def search_subtitles_by_hash(self, file_hash, language='eng'):
        """Search for subtitles by file hash using XML-RPC API."""
        self._ensure_logged_in()
        print(f"[DEBUG] Searching by hash: '{file_hash}' in language: '{language}'")
        
        # Prepare search parameters for hash search
        search_params = [{
            'sublanguageid': language,
            'moviehash': file_hash
        }]
        
        print(f"[DEBUG] Hash search params: {search_params}")
        
        try:
            response = self.server.SearchSubtitles(self.token, search_params)
            print(f"[DEBUG] Hash search response status: {response.get('status') if isinstance(response, dict) else 'Unknown'}")
            
            if isinstance(response, dict) and response.get('status') == '200 OK' and response.get('data'):
                results = response['data']
                print(f"[DEBUG] Hash search found {len(results)} results")
                
                # Convert to the same format as the REST API for compatibility
                converted_results = []
                for result in results:
                    converted_result = {
                        'id': result.get('IDSubtitleFile'),
                        'type': 'subtitle',
                        'attributes': {
                            'subtitle_id': result.get('IDSubtitle'),
                            'language': result.get('SubLanguageID'),
                            'download_count': int(result.get('SubDownloadsCnt', 0)),
                            'new_download_count': int(result.get('SubDownloadsCnt', 0)),
                            'hearing_impaired': result.get('SubHearingImpaired') == '1',
                            'hd': result.get('SubHD') == '1',
                            'fps': float(result.get('MovieFPS', 0)),
                            'upload_date': result.get('SubAddDate'),
                            'release': result.get('SubFileName'),
                            'comments': result.get('SubComments'),
                            'feature_details': {
                                'feature_id': result.get('IDMovie'),
                                'feature_type': 'Episode',
                                'year': int(result.get('MovieYear', 0)),
                                'title': result.get('MovieName'),
                                'movie_name': result.get('MovieName'),
                                'imdb_id': result.get('IDMovieImdb'),
                                'season_number': int(result.get('SeriesSeason', 0)),
                                'episode_number': int(result.get('SeriesEpisode', 0)),
                                'parent_title': result.get('MovieName')
                            },
                            'files': [{
                                'file_id': result.get('IDSubtitleFile'),
                                'cd_number': 1,
                                'file_name': result.get('SubFileName')
                            }]
                        }
                    }
                    converted_results.append(converted_result)
                
                return converted_results
            else:
                print(f"[DEBUG] Hash search found no results: {response}")
                return []
                
        except Exception as e:
            print(f"Error searching subtitles by hash: {e}")
            return []

    def download_subtitle(self, subtitle_id, output_path):
        """Download subtitle file using XML-RPC API."""
        self._ensure_logged_in()
        try:
            print(f"[DEBUG] Attempting to download subtitle with ID: {subtitle_id}")
            
            # Download subtitle using XML-RPC
            response = self.server.DownloadSubtitles(self.token, [subtitle_id])
            print(f"[DEBUG] Download response status: {response.get('status') if isinstance(response, dict) else 'Unknown'}")
            
            if isinstance(response, dict) and response.get('status') == '200 OK' and response.get('data'):
                subtitle_data = response['data'][0]
                encoded_content = subtitle_data.get('data')
                
                if encoded_content:
                    # Decode base64 and decompress gzip
                    decoded_content = base64.b64decode(encoded_content)
                    decompressed_content = gzip.decompress(decoded_content)
                    
                    # Save the subtitle file
                    output_dir = os.path.dirname(output_path)
                    if output_dir:
                        os.makedirs(output_dir, exist_ok=True)
                    
                    with open(output_path, 'wb') as f:
                        f.write(decompressed_content)
                    
                    print(f"[DEBUG] Successfully downloaded subtitle to: {output_path}")
                    return True
                else:
                    print(f"[DEBUG] No subtitle data in response")
                    return False
            else:
                print(f"[DEBUG] Download failed: {response}")
                return False
                
        except Exception as e:
            print(f"Error downloading subtitle: {e}")
            return False

    def __del__(self):
        """Logout when the object is destroyed."""
        if self.token:
            try:
                self.server.LogOut(self.token)
                print("[DEBUG] Logged out from OpenSubtitles")
            except:
                pass 