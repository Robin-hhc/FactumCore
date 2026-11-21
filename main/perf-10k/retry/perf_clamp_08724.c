/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08724(unsigned int count)
{
    const unsigned int limit = 161u;
    return count > limit ? limit : count;
}
