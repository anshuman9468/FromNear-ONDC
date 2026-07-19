class ONDCError(Exception):
    """Base exception for all ONDC protocol errors."""
    pass


class GatewayConnectionError(ONDCError):
    """Raised when the ONDC Gateway or a BPP is unreachable or returns an error response."""
    def __init__(
        self,
        message: str,
        gateway: str,
        reason: str,
        status_code: int = 502,
        response_body: str = None,
        error_type: str = None,
        error_message: str = None,
    ):
        super().__init__(message)
        self.message = message
        self.gateway = gateway
        self.reason = reason
        self.status_code = status_code
        self.response_body = response_body
        self.error_type = error_type
        self.error_message = error_message


class RegistryLookupError(ONDCError):
    """Raised when looking up public keys or registry details fails."""
    pass


class SigningConfigurationError(ONDCError):
    """Raised when mandatory signing keys/credentials are missing or invalid."""
    pass


class SignatureGenerationError(ONDCError):
    """Raised when generating authorization header signatures fails."""
    pass


class ProtocolValidationError(ONDCError):
    """Raised when incoming or outgoing payloads fail protocol checks (e.g. timestamp skew, signatures)."""
    pass
