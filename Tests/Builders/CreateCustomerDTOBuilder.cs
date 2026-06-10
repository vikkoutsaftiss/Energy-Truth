using Energy_Truth.Shared.DTO_s;
using System;
using System.Collections.Generic;
using System.Text;

namespace _04._Tests.Builders
{
    public class CreateCustomerDTOBuilder
    {
        private string _email = "test@email.nl";
        private string _name = "test";
        private string _password = "password123";
        private string _confirmPassword = "password123";
        private string _address = "123 Main St";

        public CreateCustomerDTOBuilder WithEmail(string email)
        {
            _email = email;
            return this;
        }

        public CreateCustomerDTOBuilder WithName(string name)
        {
            _name = name;
            return this;
        }

        public CreateCustomerDTOBuilder WithPassword(string password)
        {
            _password = password;
            return this;
        }

        public CreateCustomerDTOBuilder WithConfirmPassword(string confirmPassword)
        {
            _confirmPassword = confirmPassword;
            return this;
        }

        public CreateCustomerDTOBuilder WithAddress(string address)
        {
            _address = address;
            return this;
        }

        public CreateCustomerDTO Build() => new CreateCustomerDTO
        {
            Email = _email,
            Name = _name,
            Password = _password,
            ConfirmPassword = _confirmPassword,
            Address = _address
        };
    }
}