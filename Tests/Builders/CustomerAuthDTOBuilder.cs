using Energy_Truth.Shared.DTO_s;
using System;
using System.Collections.Generic;
using System.Text;

namespace _04._Tests.Builders
{
    public class CustomerAuthDTOBuilder
    {
        private int _id = 1;
        private string _email = "test@example.com";
        private string _name = "Test User";
        private string _passwordHash = BCrypt.Net.BCrypt.HashPassword("password123");
        private bool _isAdmin = false;

        public CustomerAuthDTOBuilder WithId(int id)
        {
            _id = id;
            return this;
        }

        public CustomerAuthDTOBuilder WithEmail(string email)
        {
            _email = email;
            return this;
        }

        public CustomerAuthDTOBuilder WithName(string name)
        {
            _name = name;
            return this;
        }

        public CustomerAuthDTOBuilder WithPasswordHash(string passwordHash)
        {
            _passwordHash = passwordHash;
            return this;
        }

        public CustomerAuthDTOBuilder WithIsAdmin(bool isAdmin)
        {
            _isAdmin = isAdmin;
            return this;
        }

        public CustomerAuthDTO Build()
        {
            return new CustomerAuthDTO
            {
                Id = _id,
                Email = _email,
                Name = _name,
                PasswordHash = _passwordHash,
                IsAdmin = _isAdmin
            };
        }
    }
}
