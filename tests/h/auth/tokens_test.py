# -*- coding: utf-8 -*-

import datetime

import mock
import pytest
from pyramid.testing import DummyRequest

from h import db
from h.auth import models
from h.auth import tokens


def test_generate_jwt_calls_encode(jwt, config):
    """It should pass the right arguments to encode()."""
    config.testing_securitypolicy('acct:testuser@hypothes.is')
    before = datetime.datetime.utcnow()
    request = mock_request()

    tokens.generate_jwt(request, 3600)

    assert jwt.encode.call_args[0][0]['sub'] == 'acct:testuser@hypothes.is', (
        "It should encode the userid as 'sub'")
    after = datetime.datetime.utcnow() + datetime.timedelta(seconds=3600)
    assert before < jwt.encode.call_args[0][0]['exp'] < after, (
        "It should encode the expiration time as 'exp'")
    assert jwt.encode.call_args[0][0]['aud'] == request.host_url, (
        "It should encode request.host_url as 'aud'")
    assert jwt.encode.call_args[1]['algorithm'] == 'HS256', (
        "It should pass the right algorithm to encode()")


def test_generate_jwt_when_authenticated_userid_is_None(jwt):
    """It should work when request.authenticated_userid is None."""
    request = mock_request()

    tokens.generate_jwt(request, 3600)

    assert jwt.encode.call_args[0][0]['sub'] is None


def test_generate_jwt_returns_token(jwt):
    assert (tokens.generate_jwt(mock_request(), 3600) ==
            jwt.encode.return_value)


def test_userid_from_jwt_calls_decode(jwt):
    request = mock_request()
    tokens.userid_from_jwt(u'abc123', request)

    assert jwt.decode.call_args[0] == (u'abc123',), (
        "It should pass the correct token to decode()")
    assert (jwt.decode.call_args[1]['key'] ==
            request.registry.settings['h.client_secret']), (
        "It should pass the right secret key to decode()")
    assert jwt.decode.call_args[1]['audience'] == request.host_url, (
        "It should pass the right audience to decode()")
    assert jwt.decode.call_args[1]['leeway'] == 240, (
        "It should pass the right leeway to decode()")
    assert jwt.decode.call_args[1]['algorithms'] == ['HS256'], (
        "It should pass the right algorithms to decode()")


def test_userid_from_jwt_returns_sub_from_decode(jwt):
    jwt.decode.return_value = {'sub': 'acct:test_user@hypothes.is'}

    result = tokens.userid_from_jwt(u'abc123', mock_request())

    assert result == 'acct:test_user@hypothes.is'


def test_userid_from_jwt_returns_None_if_no_sub(jwt):
    jwt.decode.return_value = {}  # No 'sub' key.

    result = tokens.userid_from_jwt(u'abc123', mock_request())

    assert result is None


def test_userid_from_jwt_returns_None_if_decoding_fails(jwt):
    class InvalidTokenError(Exception):
        pass
    jwt.InvalidTokenError = InvalidTokenError
    jwt.decode.side_effect = InvalidTokenError

    result = tokens.userid_from_jwt(u'abc123', mock_request())

    assert result is None


def test_generate_jwt_userid_from_jwt_successful(config):
    """Test generate_jwt() and userid_from_jwt() together.

    Test that userid_from_jwt() successfully decodes tokens
    generated by generate_jwt().

    """
    config.testing_securitypolicy('acct:testuser@hypothes.is')
    token = tokens.generate_jwt(mock_request(), 3600)
    userid = tokens.userid_from_jwt(token, mock_request())

    assert userid == 'acct:testuser@hypothes.is'


def test_generate_jwt_userid_from_jwt_bad_token():
    """Test generate_jwt() and userid_from_jwt() together.

    Test that userid_from_jwt() correctly fails to decode a token
    generated by generate_jwt() using the wrong secret.

    """
    request = mock_request()
    request.registry.settings['h.client_secret'] = 'wrong'
    token = tokens.generate_jwt(request, 3600)

    userid = tokens.userid_from_jwt(token, mock_request())

    assert userid is None


def test_userid_from_api_token_returns_None_when_token_doesnt_start_with_prefix():
    """
    As a sanity check, don't even attempt to look up tokens that don't start
    with the expected prefix.
    """
    request = mock_request()
    token = models.Token('acct:foo@example.com')
    token.value = u'abc123'
    db.Session.add(token)

    result = tokens.userid_from_api_token(u'abc123', request)

    assert result is None


def test_userid_from_api_token_returns_None_for_nonexistent_tokens():
    request = mock_request()
    madeuptoken = models.Token.prefix + '123abc'

    result = tokens.userid_from_api_token(madeuptoken, request)

    assert result is None


def test_userid_from_api_token_returns_userid_for_valid_tokens():
    request = mock_request()
    token = models.Token('acct:foo@example.com')
    db.Session.add(token)

    result = tokens.userid_from_api_token(token.value, request)

    assert result == 'acct:foo@example.com'


def mock_request():
    request = DummyRequest(db=db.Session)
    request.registry.settings = {
        'h.client_id': 'id',
        'h.client_secret': 'secret'
    }
    return request


@pytest.fixture
def jwt(patch):
    return patch('h.auth.tokens.jwt')
