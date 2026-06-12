using Energy_Truth.Shared.Login;
using System;
using System.Collections.Generic;
using System.Text;

namespace _04._Tests.Builders
{
    public class LoginRequestBuilder
    {
        private string _email = "test@example.com";
        private string _password = "password";

        public LoginRequestBuilder WithEmail(string email)
        {
            _email = email;
            return this;
        }

        public LoginRequestBuilder WithPassword(string password)
        {
            _password = password;
            return this;
        }

        public LoginRequestDTO Build()
        {
            return new LoginRequestDTO(_email, _password);
        }
    }
}