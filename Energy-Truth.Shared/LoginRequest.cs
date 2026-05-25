using System;
using System.Collections.Generic;
using System.Text;
using System.Text.Json.Serialization;

namespace Energy_Truth.Shared
{
    public class LoginRequest
    {
        public LoginRequest(string username, string password)
        {
            Username = username;
            Password = password;    
        }

        public string Username { get; set; }
        public string Password { get; set; }
    }
}
