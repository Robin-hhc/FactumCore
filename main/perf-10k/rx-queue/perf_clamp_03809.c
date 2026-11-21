/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03809(unsigned int count)
{
    const unsigned int limit = 21u;
    return count > limit ? limit : count;
}
