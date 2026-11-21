/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05374(unsigned int count)
{
    const unsigned int limit = 232u;
    return count > limit ? limit : count;
}
