using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Login;
using Energy_Truth_WEB_API.Services.Customer;
using Microsoft.AspNetCore.Mvc;
using Energy_Truth.Shared.Repositories;

namespace Energy_Truth_WEB_API.Controllers
{

    [ApiController]
    [Route("api/[controller]")] // Dit zorgt dat de URL /api/authentication wordt
    public class AuthenticationController : ControllerBase
    {
        private readonly ICustomerService _customerService;

        public AuthenticationController(ICustomerService customerService)
        {
            _customerService = customerService;
        }


        [HttpPost("login")] // wanneer de post actie login uitgevoerd wordt wordt deze methode aangeroepen.
        public async Task<IActionResult> Login([FromBody] LoginRequestDTO request)
        {
            if (request == null)
            {
                return BadRequest("Ongeldige aanvraag.");
            }                   

            try
            {
                var customer = await _customerService.LoginCustomerAsync(request);
                if (customer != null && customer.IsLoggedIn)
                {
                    return Ok(customer);
                }
                else
                {
                    return BadRequest("Ongeldige inloggegevens.");
                }
            }
            catch (Exception)
            {
                return StatusCode(500, $"Er is een fout opgetreden bij het inloggen. Probeer het later opnieuw.");
            }
        }



        [HttpPost("register")]
        public async Task<IActionResult> CreateCustomer([FromBody] CreateCustomerDTO registerRequest)
        {
            if (registerRequest == null)
            {
                return BadRequest("Ongeldige klantgegevens.");
            }

            if (string.IsNullOrEmpty(registerRequest.Email))
            {
                return BadRequest("E-mailadres is verplicht.");
            }

            if (string.IsNullOrEmpty(registerRequest.Password))
            {
                return BadRequest("Wachtwoord is verplicht.");
            }

            if (string.IsNullOrEmpty(registerRequest.Address))
            {
                return BadRequest("Adres is verplicht.");
            }

            try
            {
                var customerId = await _customerService.CreateCustomerAsync(registerRequest);

                if (customerId == 0)
                {
                    return BadRequest("Klant met dit e-mailadres bestaat al.");
                }

                return Ok();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Fout bij aanmaken klant: {ex.Message}");

                return StatusCode(500, $"Er is een fout opgetreden bij het aanmaken van de klant. Probeer het later opnieuw.");
            }
        }

    }
}
