from dataclasses import dataclass

@dataclass
class Token:
    bearer_token: str
    expiration: float
    main_id: str

class User:
    def __init__(self,
                 user_name: str,
                 user_id: str,
                 user_side: str):
        self.user_name = user_name.lower()
        self.user_id = user_id
        self.user_side = user_side

    def match(self, match_str):
        if match_str.lower() == self.user_name or match_str == self.user_side:
            return self.user_id
        return False