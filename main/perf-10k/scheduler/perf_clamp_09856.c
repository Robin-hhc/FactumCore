/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09856(unsigned int count)
{
    const unsigned int limit = 232u;
    return count > limit ? limit : count;
}
