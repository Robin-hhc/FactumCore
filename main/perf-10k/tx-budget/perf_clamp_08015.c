/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08015(unsigned int count)
{
    const unsigned int limit = 60u;
    return count > limit ? limit : count;
}
