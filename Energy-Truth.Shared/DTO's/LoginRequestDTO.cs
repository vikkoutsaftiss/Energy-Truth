using System;
using System.Collections.Generic;
using System.Text;
using System.Text.Json.Serialization;

namespace Energy_Truth.Shared.Login
{
    public class LoginRequestDTO
    {
        public LoginRequestDTO(string email, string password)
        {
            Email = email;
            Password = password;    
        }

        public string Email { get; set; }
        public string Password { get; set; }
    }
}
