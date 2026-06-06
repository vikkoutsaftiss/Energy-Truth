using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Text;

namespace Energy_Truth.Shared.DTO_s
{
    public class CreateCustomerDTO
    {
        [Required(ErrorMessage = "Email is verplicht")]
        public string Email { get; set; }
        [Required(ErrorMessage = "Naam is verplicht")]
        public string Name { get; set; }
        [Required(ErrorMessage = "Wachtwoord is verplicht")]
        public string Password { get; set; }
        [Required(ErrorMessage = "Bevestiging van wachtwoord is verplicht")]
        public string ConfirmPassword { get; set; }
        [Required(ErrorMessage = "Adres is verplicht")]
        public string Address { get; set; }
    }
}
