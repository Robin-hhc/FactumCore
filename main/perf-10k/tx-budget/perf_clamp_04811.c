/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04811(unsigned int count)
{
    const unsigned int limit = 123u;
    return count > limit ? limit : count;
}
