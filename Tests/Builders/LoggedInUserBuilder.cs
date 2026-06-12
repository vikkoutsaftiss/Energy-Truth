using Energy_Truth.Shared.Login;
using System;
using System.Collections.Generic;
using System.Text;

namespace _04._Tests.Builders
{
    public class LoggedInUserBuilder
    {
        private int _id = 1;
        private string _name = "Test User";
        private string _email = "test@example.com";
        private bool _isLoggedIn = true;
        private bool _isAdmin = false;

        public LoggedInUserBuilder WithId(int id)
        {
            _id = id;
            return this;
        }

        public LoggedInUserBuilder WithName(string name)
        {
            _name = name;
            return this;
        }

        public LoggedInUserBuilder WithEmail(string email)
        {
            _email = email;
            return this;
        }

        public LoggedInUserBuilder WithIsLoggedIn(bool isLoggedIn)
        {
            _isLoggedIn = isLoggedIn;
            return this;
        }

        public LoggedInUserBuilder WithIsAdmin(bool isAdmin)
        {
            _isAdmin = isAdmin;
            return this;
        }

        public LoggedInUser Build() => new LoggedInUser
        {
            Id = _id,
            Name = _name,
            Email = _email,
            IsLoggedIn = _isLoggedIn,
            IsAdmin = _isAdmin
        };
    }
}
