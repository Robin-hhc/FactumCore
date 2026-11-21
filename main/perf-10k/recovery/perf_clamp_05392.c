/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05392(unsigned int count)
{
    const unsigned int limit = 40u;
    return count > limit ? limit : count;
}
